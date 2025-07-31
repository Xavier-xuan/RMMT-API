import decimal
import json
import numpy as np

import arrow
from apscheduler.schedulers.blocking import BlockingScheduler

from sqlalchemy.orm import joinedload

import config
from models import *

from text2vec import cos_sim, SentenceModel


model = SentenceModel()

def scan_students():
    if not is_in_calculating_time():
        output("当前时间不在算法匹配时间段内")
        return
    else:
        output("开始进行算法匹配")

    students = db_session.query(Student).all()

    students = [student for student in students if student.has_answered_questionnaire()]
    student_ids = [[], [], []]  # 0 None,  1 male, 2 female
    id_to_students = {}

    for student in students:
        student_ids[student.gender].append(student.id)
        id_to_students[student.id] = student

    for student in students:
        output("正在检测学生 {}({}) 的匹配列表是否完整".format(student.name, student.id))
        # 已经计算了匹配分数的id
        existed_ids = [id[0]
                       for id
                       in db_session.query(MatchingScore.to_student_id)
                       .filter(MatchingScore.from_student_id == student.id)
                       .all()
                       ]

        matching_scores = []

        # compare
        for target_student_id in student_ids[student.gender]:
            if target_student_id not in existed_ids:
                if target_student_id == student.id:
                    continue

                from_student = student
                to_student = id_to_students[target_student_id]
                output("正在计算学生 {}({}) 对 {}({}) 的匹配分数".format(from_student.name, from_student.id,
                                                                         to_student.name,
                                                                         to_student.id))
                score = get_score(from_student=from_student, to_student=to_student)
                score = decimal.Decimal(score).quantize(decimal.Decimal('0.00'))
                matching_scores.append(
                    MatchingScore(from_student_id=from_student.id, to_student_id=to_student.id, score=score)
                )
                output("计算完成")

        db_session.bulk_save_objects(matching_scores)
        db_session.commit()

    output("算法匹配完成")


def get_student_by_id(student_id, students):
    student = db_session.query(Student) \
        .options(
        joinedload(Student.sent_matching_scores), joinedload(Student.questionnaire_answers)) \
        .group_by(Student) \
        .filter(Student.id == student_id).first()

    return student


def get_score(from_student, to_student):
    to_student_questionnaire_answers = sorted(to_student.questionnaire_answers, key=lambda x: x.item_id)
    from_student_questionnaire_answers = sorted(from_student.questionnaire_answers, key=lambda x: x.item_id)
    
    question_match = {}
    changes = False
    i = j = 0
    
    while i < len(to_student_questionnaire_answers) and j < len(from_student_questionnaire_answers):
        to_answer = to_student_questionnaire_answers[i]
        from_answer = from_student_questionnaire_answers[j]
        
        if to_answer.item_id < from_answer.item_id:
            i += 1
            continue
        if to_answer.item_id > from_answer.item_id:
            j += 1
            continue
            
        # 相同item_id的问题
        if to_answer.weight <= 0:
            i += 1
            j += 1
            continue
            
        # 判断是否是数值型答案（简单启发式方法）
        if is_numeric_answer(to_answer.answer) and is_numeric_answer(from_answer.answer):
            # 数值型答案的相似度计算
            try:
                num1 = float(to_answer.answer)
                num2 = float(from_answer.answer)
                # 使用简单的反比例函数计算相似度（值越接近相似度越高）
                diff = abs(num1 - num2)
                value = 1 / (1 + diff)  # 保证结果在0-1之间
            except ValueError:
                value = 0
        else:
            # 文本型答案的相似度计算（保持原逻辑）
            if not to_answer.vector:
                to_answer.vector = json.dumps(model.encode(to_answer.answer).tolist())
                changes = True
            if not from_answer.vector:
                from_answer.vector = json.dumps(model.encode(from_answer.answer).tolist())
                changes = True
                
            vec1 = np.array(json.loads(to_answer.vector))
            vec2 = np.array(json.loads(from_answer.vector))
            value = cos_sim(vec1, vec2).item()
            
        question_match[to_answer.item_id] = (value, to_answer.weight)
        i += 1
        j += 1
    
    # 计算加权平均分
    total_weight = sum(float(w) for _, w in question_match.values())
    if total_weight > 0:
        weighted_sum = sum(float(v) * float(w) for v, w in question_match.values())
        score = (weighted_sum / total_weight) * 100
    else:
        score = 0
    
    if changes:
        db_session.commit()
        
    return score

def is_numeric_answer(answer):
    """简单判断是否是数值型答案"""
    try:
        float(answer)
        return True
    except ValueError:
        return False



def is_in_calculating_time():
    start_time_string = db_session.query(SystemSetting.value).filter(SystemSetting.key == "step_2_start_at").first()[0]
    stop_time_string = db_session.query(SystemSetting.value).filter(SystemSetting.key == "step_2_end_at").first()[0]
    start_time = arrow.get(start_time_string, tzinfo="Asia/Shanghai")
    stop_time = arrow.get(stop_time_string, tzinfo="Asia/Shanghai")
    return start_time <= arrow.now("Asia/Shanghai") <= stop_time


def output(message):
    time_prefix = "[{}] ".format(arrow.now("Asia/Shanghai").format("YYYY-MM-DD HH:mm:ss"))
    print(time_prefix + message)


if __name__ == '__main__':
    scheduler = BlockingScheduler(job_defaults={
        'coalesce': True,
        'max_instances': 1
    })

    scheduler.add_job(scan_students, "interval", seconds=config.GeneralConfig.ASYNC_JOB_SCAN_INTERVAL)

    scheduler.start()
