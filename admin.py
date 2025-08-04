import copy
import datetime
from functools import wraps

import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, verify_jwt_in_request, get_jwt, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, func

from database import db_session
from models import Admin, Student, Team, ExchangingNeed, CustomQuestionnaireItem, SystemSetting, QuestionnaireItem, \
    MatchingScore, QuestionnaireAnswer, TeamRequest, TeamInvitation, get_system_setting, CustomQuestionnaireAnswer, \
    ExchangingRequest

admin_pages = Blueprint('admin_pages', __name__, template_folder="templates/admin")

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims["role"] == "admin":
                return fn(*args, **kwargs)
            else:
                return jsonify({
                    "code": 403,
                    "msg": "无权限！"
                }), 403

        return decorator

    return wrapper


@admin_pages.route('/login', methods=['POST'])
def login():
    if request.json is not None:
        email = request.json.get('email', None)
        password = request.json.get('password', None)
        admin = db_session.query(Admin).where(Admin.email == email).first()
        if admin is not None and admin.check_password(password):
            admin.last_logged_at = datetime.datetime.now()
            db_session.commit()
            access_token = create_access_token(identity=admin.id, additional_headers={
                "role": "admin"
            }, additional_claims={
                "role": "admin"
            })

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {
                    "access_token": access_token
                }
            })

    return jsonify({
        "code": 401,
        "msg": "邮箱地址或密码错误！"
    })


@admin_pages.post('/logout')
@admin_required()
def logout():
    return jsonify({
        "code": 200,
        "msg": "success"
    })


@admin_pages.get("/userinfo")
@admin_required()
def userinfo():
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "user": current_user.to_dict(rules=['-password'])
        }
    })


@admin_pages.post("/change_password")
@admin_required()
def change_password():
    if request.json is not None:
        current_pw = request.json.get('current_password')
        new_pw = request.json.get('new_password')
        if len(new_pw) < 8:
            return jsonify({
                "code": 400,
                "msg": "密码不能小于八位"
            })
        if not current_user.check_password(current_pw):
            return jsonify({
                "code": 400,
                "msg": "旧密码不正确"
            })

        hashed_pw = bcrypt.hashpw(bytes(new_pw, encoding='utf8'), bcrypt.gensalt())
        current_user.password = hashed_pw
        db_session.commit()
        return jsonify({
            "code": 200,
            "msg": "success"
        })


@admin_pages.get("/student/list")
@admin_required()
def student_list():
    students = (
        db_session.query(
            Student.id,
            Student.name,
            Student.last_logged_at,
            Student.gender,
            Student.category,
            Student.created_at,
            Student.team_id,
            Team.id.label("team_id"),
            Team.description.label("team_description"),
            func.count(QuestionnaireAnswer.id).label("answers_count")
        )
        .outerjoin(Team)  # Explicit join with Team
        .outerjoin(QuestionnaireAnswer)  # Outer join with QuestionnaireAnswers, only if answers need to be counted
        .group_by(Student.id, Team.id)
        .all()
    )

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "students": [{
                "id": student.id,
                "name": student.name,
                "team": {
                    "id": student.team_id,
                    "description": student.team_description
                } if student.team_id else None,
                "last_logged_at": student.last_logged_at,
                "gender": student.gender,
                "created_at": student.created_at,
                "has_answered_questionnaire": student.answers_count > 0,
                "team_id": student.team_id,
                "category": student.category
            } for student in students]
        }
    })


@admin_pages.post("/student/import")
@admin_required()
def student_import():
    if request.json is not None and request.json.get("students", None) is not None:
        students = request.json.get("students")

        data_to_store = []
        students_id_in_store = [item[0] for item in db_session.query(Student.id).all()]
        for student in copy.deepcopy(students):
            # 导入时要把学生姓名里的空格替换为#
            space_count = student.split()
            if len(space_count) != 5:
                continue
            id, name, gender, category, password = space_count
            id = int(id)

            # 查重
            if id in students_id_in_store:
                continue
            else:
                students_id_in_store.append(id)
                students.remove(student)

            name = name.replace("#", " ")
            password = bcrypt.hashpw(bytes(password, encoding="utf8"), bcrypt.gensalt())
            data_to_store.append(
                Student(id=id, name=name, gender=gender, category=category, password=password, last_logged_at=None)
            )

        db_session.bulk_save_objects(data_to_store)

        db_session.commit()

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "fail_to_import": students
            }
        })

    return jsonify({
        "code": 406,
        "msg": "获取数据失败"
    })


@admin_pages.post("/student/update")
@admin_required()
def student_update():
    if request.json is not None:
        student_id = request.json.get('id')
        name = request.json.get('name')
        contact = request.json.get('contact')
        gender = request.json.get('gender')
        password = request.json.get('password', None)
        team_id = request.json.get('team_id', None)
        category = request.json.get('category', None)
        student = db_session.query(Student).get(student_id)

        if student is not None:
            result = student.set_team(team_id)
            if result is not True:
                return result

            student.name = name
            student.contact = contact
            student.gender = gender
            if category is not None:
                student.category = category

            if password is not None:
                hashed_password = bcrypt.hashpw(bytes(password, encoding='utf8'), bcrypt.gensalt())
                student.password = hashed_password

            db_session.commit()

            return jsonify({
                "code": 200,
                "msg": "success"
            })

        else:
            return jsonify({
                "code": 404,
                "msg": "学生不存在"
            })

    return jsonify({
        "code": 400,
        "msg": "更新失败"
    })


@admin_pages.get('/student/info')
@admin_required()
def student_info():
    if request.args is not None:
        id = request.args.get('student_id', None)
        student = db_session.query(Student).filter(Student.id == id) \
            .outerjoin(Team).outerjoin(CustomQuestionnaireItem).outerjoin(ExchangingNeed).first()
        if student is not None:
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {
                    "student": student.to_dict(only=[
                        'id', 'name', 'last_logged_at', 'contact', 'qq', 'wechat', 'province', 'mbti', 'category', 'team_id', 'questionnaire_answers', 'gender',
                        'team.students.name', 'team.students.id', 'team.description', 'team_requests.id',
                        'team_requests.team_id'
                    ])
                }
            })

    return jsonify({
        "code": 404,
        "msg": "学生不存在"
    })


@admin_pages.post('/student/questionnaire')
@admin_required()
def student_questionnaire():
    if request.json is not None:
        id = request.json.get('student_id', None)
        questionnaire_answers = request.json.get('questionnaire_answers')

        if type(questionnaire_answers) is not dict:
            return jsonify({
                "code": 400,
                "msg": "问卷答案数据错误"
            })
        student = db_session.query(Student).get(id)
        if student is None:
            return jsonify({
                "code": 404,
                "msg": "学生不存在"
            })

        exist_answers = student.questionnaire_answers
        questionnaire_items = db_session.query(QuestionnaireItem).all()
        default_weight = {}
        missed_items = []
        for questionnaire_item in questionnaire_items:
            default_weight[questionnaire_item.id] = questionnaire_item.weight

        bulk_save_models = []
        data_changed = False
        for key in questionnaire_answers.keys():
            value = questionnaire_answers[key]
            if key not in default_weight.keys():
                # 找不对对应item 存个屁
                missed_items.append((key, value))
                continue
            elif default_weight[key] < 0:
                value['weight'] = default_weight[key]

            need_to_create = True

            # 对已存在的答案进行修改 一般只会用到这一个
            for exist_answer in exist_answers:
                if exist_answer.item_id == key:
                    need_to_create = False
                    if exist_answer.answer != str(value['answer']) or exist_answer.weight != value['weight']:
                        exist_answer.answer = str(value['answer'])
                        exist_answer.weight = value['weight']
                        exist_answer.updated_at = datetime.datetime.now()
                        db_session.commit()
                        data_changed = True

            if need_to_create:
                new_answer = QuestionnaireAnswer(item_id=key, answer=str(value['answer']), student_id=student.id,
                                                 weight=value['weight'])
                bulk_save_models.append(new_answer)
                data_changed = True

        # 重头戏 存数据

        if data_changed:
            db_session.bulk_save_objects(bulk_save_models)
            db_session.commit()

            # 删除匹配得分
            db_session.query(MatchingScore) \
                .filter((MatchingScore.to_student_id == student.id) | (
                    MatchingScore.from_student_id == student.id)) \
                .delete(synchronize_session=False)

            db_session.commit()

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "fail_to_save": missed_items
            }
        })


@admin_pages.delete('/student/delete')
@admin_required()
def student_delete():
    if request.json is not None:
        id = request.json.get('student_id', None)
        student = db_session.query(Student).get(id)
        if student is not None:
            db_session.query(MatchingScore).where(or_(MatchingScore.from_student_id == student.id, MatchingScore.to_student_id == student.id)).delete()
            db_session.query(TeamInvitation).where(TeamInvitation.from_student_id == student.id).delete()
            db_session.query(TeamInvitation).where(TeamInvitation.to_student_id == student.id).update({
                TeamInvitation.to_student_id: 0,
                TeamInvitation.status: -2,
                TeamInvitation.reason: "目标用户已被删除"
            })

            db_session.delete(student)
            db_session.commit()

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@admin_pages.get('/system_setting/list')
@admin_required()
def system_setting_list():
    system_settings = db_session.query(SystemSetting).all()
    system_settings = [system_setting.to_dict() for system_setting in system_settings]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": system_settings
    })


@admin_pages.get('/system_setting/get')
@admin_required()
def system_setting_get():
    key = request.args.get('key', None)
    if key is not None:
        system_setting = db_session.query(SystemSetting).filter(SystemSetting.key == key).first()
        if system_setting is None:
            value = None
        else:
            value = system_setting.value
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                key: value
            }
        })

    return jsonify({
        "code": 400,
        "msg": "缺少必要参数"
    })


@admin_pages.post('/system_setting/update')
@admin_required()
def system_setting_update():
    if request.json is not None:
        for key, value in request.json.items():
            item_in_db = db_session.query(SystemSetting).filter(SystemSetting.key == key).first()
            if item_in_db is not None:
                if item_in_db.value == value:
                    continue
                item_in_db.value = value
                item_in_db.updated_at = datetime.datetime.now()

            else:
                item = SystemSetting(key=key, value=value)
                db_session.add(item)

            db_session.commit()

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@admin_pages.delete('/system_setting/delete')
@admin_required()
def system_setting_delete():
    if request.json is not None:
        key = request.json.get('key', None)
        item = db_session.query(SystemSetting).filter(SystemSetting.key == key).first()

        if item is not None:
            db_session.delete(item)
            db_session.commit()

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@admin_pages.get('/questionnaire/list')
@admin_required()
def questionnaire_list():
    questionnaire_items = db_session.query(QuestionnaireItem).order_by(QuestionnaireItem.index.asc()).all()

    questionnaire_items = [questionnaire_item.to_dict() for questionnaire_item in questionnaire_items]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": questionnaire_items
    })


@admin_pages.post('/questionnaire/set')
@admin_required()
def questionnaire_set():
    if request.json is not None:
        # 删除所有的匹配分
        # 删除所有的问卷答案
        old_items = [MatchingScore, QuestionnaireAnswer, QuestionnaireItem]
        for old_item in old_items:
            db_session.query(old_item).delete()
            db_session.commit()

        # 重新写入
        item_list = []

        for piece in request.json:
            title = piece.get('title', None)
            weight = piece.get('weight', None)
            data_type = piece.get('data_type', None)
            params = piece.get('params', "{}")
            index = piece.get('index', None)
            id = piece.get('id', None)
            type = piece.get('type', 'text')
            if type == 'text':
                weight = 0

            item = QuestionnaireItem(
                title=title,
                weight=weight,
                data_type=data_type,
                params=str(params),
                index=index,
                id=id,
                type=type
            )
            item_list.append(item)

        db_session.bulk_save_objects(item_list)
        db_session.commit()

        return jsonify({
            "code": 200,
            "msg": "success"
        })


@admin_pages.post('/system_reset/perform')
@admin_required()
# @jwt_required(fresh=True)
def system_reset():
    if request.json is None:
        return jsonify({
            "code": 400,
            "msg": "密码不能为空"
        })

    password = request.json.get("password")

    # check_password
    if not current_user.check_password(password):
        return jsonify({
            "code": 400,
            "msg": "密码错误"
        })

    # 删除matching scores
    db_session.query(MatchingScore).delete()

    # 删除所有自定义问卷答案
    db_session.query(CustomQuestionnaireAnswer).delete()

    # 删除所有自定义问卷
    db_session.query(CustomQuestionnaireItem).delete()

    # 删除所有问卷答案
    db_session.query(QuestionnaireAnswer).delete()

    # 删除所有组队邀请信息
    db_session.query(TeamInvitation).delete()

    # 删除所有组队请求
    db_session.query(TeamRequest).delete()

    # 删除所有组队信息
    db_session.query(Team).delete()

    # 删除所有交换请求
    db_session.query(ExchangingNeed).delete()
    db_session.query(ExchangingRequest).delete()

    # 删除所有学生账号
    db_session.query(Student).delete()

    db_session.commit()

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@admin_pages.get('/team/list')
@admin_required()
def team_list():
    teams = db_session.query(Team).options(joinedload(Team.students)).all()

    teams = [team.to_dict(only=['id', 'gender', 'category', 'description', 'created_at', 'students.id', 'students.name']) for team
             in teams]
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "teams": teams
        }
    })


@admin_pages.post('/team/join')
@admin_required()
def team_join():
    if request.json is not None:
        team_id = request.json.get('team_id', None)
        student_id = request.json.get('student_id', None)

        student = db_session.query(Student).get(student_id)

        if student is not None:
            if student.team_id is not None:
                return jsonify({
                    "code": 400,
                    "msg": "学生已经在其他队伍中，请先退出再加入"
                })

            team = db_session.query(Team).get(team_id)

            if team is None:
                return jsonify({
                    "code": 404,
                    "msg": "队伍不存在"
                })
            if int(student.gender) != int(team.gender):
                return jsonify({
                    "code": 400,
                    "msg": "性别不同，不能男女混寝"
                })

        students_count_in_team = db_session.query(Student).where(Student.team_id == team_id).count()

        if int(students_count_in_team) >= int(get_system_setting("team_max_student_count", 4)):
            return jsonify({
                "code": 400,
                "msg": "该队伍人数已满"
            })

        student.team_id = team_id
        db_session.commit()
        return jsonify({
            "code": 200,
            "msg": "success"
        })


@admin_pages.post('/team/kick')
@admin_required()
def team_kick():
    if request.json is not None:
        student_id = request.json.get('student_id', None)
        student = db_session.query(Student).get(student_id)
        if student is not None:
            if student.team is None:
                return jsonify({
                    "code": 400,
                    "msg": "学生未加入任何队伍"
                })

            # if len(student.team.students) <= 2:
            #     # 清退队伍里的所有学生 并删除队伍
            #     team = deepcopy(student.team)
            #     for item in student.team.students:
            #         item.team_id = None
            #
            #     db_session.bulk_save_objects(student.team.students)
            #     db_session.commit()
            #
            #     db_session.delete(team)
            #     db_session.commit()
            #     return jsonify({
            #         "code": 200,
            #         "msg": "success",
            #         "delete_team": True,
            #         "delete_team_id": team.id
            #     })

            student.team_id = None
            db_session.commit()

            return jsonify({
                "code": 200,
                "msg": "success"
            })


@admin_pages.delete('/team/delete')
@admin_required()
def team_delete():
    if request.json is not None:
        team_id = request.json.get('team_id', None)
        team = db_session.query(Team).get(team_id)

        if team is None:
            return jsonify({
                "code": 200,
                "msg": "success"
            })

        for student in team.students:
            student.team_id = None

        db_session.query(TeamInvitation).where(TeamInvitation.team_id == team_id).update({
            TeamInvitation.team_id: None
        })

        db_session.bulk_save_objects(team.students)

        db_session.delete(team)
        db_session.commit()

        return jsonify({
            "code": 200,
            "msg": "success"
        })


@admin_pages.post('/team/create')
@admin_required()
def team_create():
    if request.json is not None:
        description = request.json.get("description", None)
        gender = request.json.get("gender", 1)

        team = Team(description=description, gender=gender)

        db_session.add(team)
        db_session.commit()

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "team_id": team.id
            }
        })


@admin_pages.post('/team/add_student')
@admin_required()
def team_add_student():
    if request.json is not None:
        student_ids = request.json.get('students')
        team_id = request.json.get('team_id')

        # 判断空队伍不能用 Student.team_id is None
        students = db_session.query(Student) \
            .filter(Student.id.in_(student_ids)) \
            .filter(Student.team_id.is_(None)) \
            .all()

    if len(students) is not len(student_ids):
        for student in students:
            student_ids.remove(student.id)

        return jsonify({
            "code": 400,
            "msg": "部分学生不存在于数据库中，或已经加入其他队伍",
            "data": {
                "students_not_found": student_ids
            }
        })
    else:
        for student in students:
            result = student.set_team(team_id)
            if result is not True:
                # Rollback
                db_session.query(Student).filter(Student.id.in_(student_ids)).update({
                    Student.team_id: None
                })
                db_session.commit()

                return result

        return jsonify({
            "code": 200,
            "msg": "success"
        })
