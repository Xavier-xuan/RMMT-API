import decimal
import json
import numpy as np

import arrow
from apscheduler.schedulers.blocking import BlockingScheduler

from sqlalchemy.orm import joinedload

import config
from models import *

from text2vec import cos_sim

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
    to_student_questionnaire_answers = to_student.questionnaire_answers
    from_student_questionnaire_answers = from_student.questionnaire_answers

    question_match = {}

    # 计算两个学生的问卷答案的余弦相似度
    # 查询效率是否有优化空间？ O(n^2) -> O(nlogn)
    to_student_questionnaire_answers.sort(key=lambda x: x.item_id)
    from_student_questionnaire_answers.sort(key=lambda x: x.item_id)
    
    i = 0 # to_student_questionnaire_answers index
    j = 0 # from_student_questionnaire_answers index
    while i < len(to_student_questionnaire_answers) and j < len(from_student_questionnaire_answers):
        to_student_answer = to_student_questionnaire_answers[i]
        from_student_answer = from_student_questionnaire_answers[j]
        # output("type: {}, to_student_answer: {}, from_student_answer: {}".format(type(to_student_answer.vector), to_student_answer.vector, from_student_answer.vector))
        to_student_answer_vector = np.array(json.loads(to_student_answer.vector))
        from_student_answer_vector = np.array(json.loads(from_student_answer.vector))
        
        if to_student_answer.item_id == from_student_answer.item_id:
            i += 1
            j += 1
            if to_student_answer.weight <= 0:
                continue
            value = cos_sim(to_student_answer_vector, from_student_answer_vector)
            value = value.item()
            question_match[to_student_answer.item_id] = (value, to_student_answer.weight)
        elif to_student_answer.item_id < from_student_answer.item_id:
            i += 1
        else:
            j += 1
    
    # 计算加权后的余弦相似度
    cosine_similarity = np.sum([float(value) * float(weight) for value, weight in question_match.values()])
    cosine_similarity /= np.sum([float(weight) for value, weight in question_match.values()])

    # 将余弦相似度转换为分数（0-100）
    score = cosine_similarity * 100
    output("score: {}".format(score))
    return score

# Not used
def calculate_cosine_similarity(vector1, vector2, weights):
    weighted_dot_product = np.dot(weights * vector1, vector2)
    weighted_magnitude1 = np.sqrt(np.dot(weights, vector1 ** 2))
    weighted_magnitude2 = np.sqrt(np.dot(weights, vector2 ** 2))
    if weighted_magnitude1 == 0 or weighted_magnitude2 == 0:
        return 0
    return weighted_dot_product / (weighted_magnitude1 * weighted_magnitude2)

# Not used
def get_answer_values(from_student_answer, to_student_answer):
    data_type = from_student_answer.item.data_type
    if data_type == "number":
        try:
            from_answer = int(from_student_answer.answer.replace('"', ""))
            to_answer = int(to_student_answer.answer.replace('"', ""))
            return from_answer, to_answer
        except ValueError:
            return None, None
    elif data_type == "time":
        from_answer = time_difference_in_seconds(from_student_answer.answer)
        to_answer = time_difference_in_seconds(to_student_answer.answer)
        return from_answer, to_answer
    elif data_type == "date":
        from_answer = date_difference_in_days(from_student_answer.answer)
        to_answer = date_difference_in_days(to_student_answer.answer)
        return from_answer, to_answer
    elif data_type.endswith("_array"):
        from_answer_array = json.loads(from_student_answer.answer)
        to_answer_array = json.loads(to_student_answer.answer)
        if data_type == "number_array":
            return np.mean(from_answer_array), np.mean(to_answer_array)
        elif data_type == "time_array":
            from_answer = [time_difference_in_seconds(t)/60 for t in from_answer_array]
            to_answer = [time_difference_in_seconds(t)/60 for t in to_answer_array]
            return np.mean(from_answer), np.mean(to_answer)
        elif data_type == "date_array":
            from_answer = [date_difference_in_days(d) for d in from_answer_array]
            to_answer = [date_difference_in_days(d) for d in to_answer_array]
            return np.mean(from_answer), np.mean(to_answer)
        elif data_type == "text_array":
            return len(set(from_answer_array)), len(set(to_answer_array))
    return None, None

# Not used
def date_difference_in_days(date_string):
    date = arrow.get(date_string)
    return (date - arrow.get('1970-01-01')).total_seconds() / 86400

# Not used
def time_difference_in_seconds(time_string):
    time = arrow.get(time_string, "HH:mm:ss")
    return time.hour * 3600 + time.minute * 60 + time.second

# Not used
def get_questionnaire_answer_by_item_id(item_id, questionnaire_answers):
    for questionnaire_answer in questionnaire_answers:
        if questionnaire_answer.item_id == item_id:
            return questionnaire_answer

    return None


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
