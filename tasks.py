import decimal
import json
import math

import arrow
from apscheduler.schedulers.blocking import BlockingScheduler

from sqlalchemy.orm import joinedload

import config
from models import *


def scan_students():
    if not is_in_calculating_time():
        print("当前时间不在算法匹配时间段内")
        return
    else:
        print("开始进行算法匹配")

    students = db_session.query(Student) \
        .options(
        joinedload(Student.sent_matching_scores), joinedload(Student.questionnaire_answers)) \
        .group_by(Student).all()

    students = [student for student in students if student.has_answered_questionnaire()]
    student_ids = [[], [], []]  # 0 None,  1 male , 2 female

    for student in students:
        student_ids[student.gender].append(student.id)

    for student in students:
        print("正在检测学生 {}({}) 的匹配列表是否完整".format(student.name, student.id))
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
                to_student = get_student_by_id(target_student_id, students)
                print("正在计算学生 {}({}) 对 {}({}) 的匹配分数".format(from_student.name, from_student.id, to_student.name,
                                                            to_student.id))
                score = get_score(from_student=from_student, to_student=to_student)
                matching_scores.append(
                    MatchingScore(from_student_id=from_student.id, to_student_id=to_student.id, score=math.ceil(score))
                )
                print("计算完成")

        db_session.bulk_save_objects(matching_scores)
        db_session.commit()

    print("算法匹配完成")


def get_student_by_id(student_id, students):
    for student in students:
        if student_id == student.id:
            return student

    return None


def get_score(from_student, to_student):
    to_student_questionnaire_answers = to_student.questionnaire_answers
    from_student_questionnaire_answers = from_student.questionnaire_answers
    score = 0

    for to_student_answer in to_student_questionnaire_answers:
        if to_student_answer.weight <= 0:
            continue

        from_student_answer = get_questionnaire_answer_by_item_id(to_student_answer.item_id,
                                                                  from_student_questionnaire_answers)

        if from_student_answer is None:
            continue

        if from_student_answer.item.data_type == "text":
            continue

        sub_score = calculate_score(from_student_answer, to_student_answer)
        score += sub_score

        score = math.sqrt(score)
        if score >= 2147483647:
            score = 2147483647

    return score


def calculate_score(from_student_answer, to_student_answer):
    data_type = from_student_answer.item.data_type;
    if data_type == "number":
        from_answer = int(from_student_answer.answer)
        to_answer = int(to_student_answer.answer)
        difference = decimal.Decimal((from_answer - to_answer)) * to_student_answer.weight
        return math.pow(difference, 2)
    elif data_type == "time":
        from_answer = from_student_answer.answer
        to_answer = to_student_answer.answer
        difference = decimal.Decimal(time_difference_in_seconds(from_answer, to_answer)) \
                     * to_student_answer.weight
        return math.pow(difference, 2)
    elif data_type == "date":
        difference = decimal.Decimal(date_difference_in_days(from_student_answer.answer, to_student_answer.answer)) \
                     * to_student_answer.weight
        return math.pow(difference, 2)

    elif data_type.endswith("_array"):
        start_answer_array = json.loads(from_student_answer.answer)
        to_answer_array = json.loads(to_student_answer.answer)

        if data_type == "number_array":
            start_difference = start_answer_array[0] - to_answer_array[0]
            end_difference = start_answer_array[0] - to_answer_array[1]
            return range_difference(start_difference, end_difference, to_student_answer.weight)
        elif data_type == "time_array":
            start_difference = time_difference_in_seconds(start_answer_array[0], to_answer_array[0])
            end_difference = time_difference_in_seconds(start_answer_array[1], to_answer_array[1])
            return range_difference(start_difference, end_difference, to_student_answer.weight)
        elif data_type == "date_array":
            start_difference = date_difference_in_days(start_answer_array[0], to_answer_array[0])
            end_difference = date_difference_in_days(start_answer_array[1], to_answer_array[1])
            return range_difference(start_difference, end_difference, to_student_answer.weight)
        elif data_type == "text_array":
            return len(set(start_answer_array).difference(set(to_student_answer)))

    return 0


def range_difference(start_difference, end_difference, weight):
    if start_difference < 0:
        start_difference = 0

    if end_difference < 0:
        end_difference = 0

    return math.pow(decimal.Decimal(start_difference) * weight, 2) + math.pow(decimal.Decimal(end_difference) * weight,
                                                                              2)


def date_difference_in_days(date1_string, date2_string):
    date1 = arrow.get(date1_string)
    date2 = arrow.get(date2_string)
    return (date1 - date2).total_seconds() / 86400


def time_difference_in_seconds(time1_string, time2_string):
    time1 = arrow.get(time1_string, "HH:mm:ss")
    time2 = arrow.get(time2_string, "HH:mm:ss")
    return (time1 - time2).total_seconds()


def get_questionnaire_answer_by_item_id(item_id, questionnaire_answers):
    for questionnaire_answer in questionnaire_answers:
        if questionnaire_answer.item_id == item_id:
            return questionnaire_answer

    return None


def is_in_calculating_time():
    start_time_string = db_session.query(SystemSetting.value).filter(SystemSetting.key == "step_2_start_at").first()[0]
    stop_time_string = db_session.query(SystemSetting.value).filter(SystemSetting.key == "step_2_end_at").first()[0]
    start_time = arrow.get(start_time_string)
    stop_time = arrow.get(stop_time_string)
    return start_time <= arrow.now() <= stop_time


if __name__ == '__main__':
    scheduler = BlockingScheduler(job_defaults={
        'coalesce': True,
        'max_instances': 1
    })

    scheduler.add_job(scan_students, "interval", seconds=config.GeneralConfig.ASYNC_JOB_SCAN_INTERVAL)

    scheduler.start()
