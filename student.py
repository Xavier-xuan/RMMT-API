import datetime
from functools import wraps

import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, verify_jwt_in_request, get_jwt, current_user
from sqlalchemy.orm import joinedload

from database import db_session
from models import Student, QuestionnaireItem, QuestionnaireAnswer, MatchingScore, Team, TeamInvitation, \
    TeamRequest, get_system_setting

student_pages = Blueprint('student_pages', __name__, template_folder="templates/student")


def student_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims["role"] == "student":
                return fn(*args, **kwargs)
            else:
                return jsonify({
                    "code": 403,
                    "msg": "无权限！"
                }), 403

        return decorator

    return wrapper


def in_step_1_period():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            start_at = datetime.datetime.strptime(get_system_setting('step_1_start_at'), "%Y-%m-%d %H:%M:%S")
            end_at = datetime.datetime.strptime(get_system_setting('step_1_end_at'), "%Y-%m-%d %H:%M:%S")
            if start_at <= datetime.datetime.now() <= end_at:
                return fn(*args, **kwargs)
            else:
                return jsonify({
                    "code": "400",
                    "msg": "未到个人信息补充系统开放时间"
                }), 200

        return decorator

    return wrapper


def in_step_2_period():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            start_at = datetime.datetime.strptime(get_system_setting('step_2_start_at'), "%Y-%m-%d %H:%M:%S")
            end_at = datetime.datetime.strptime(get_system_setting('step_2_end_at'), "%Y-%m-%d %H:%M:%S")
            if start_at <= datetime.datetime.now() <= end_at:
                return fn(*args, **kwargs)
            else:
                return jsonify({
                    "code": "400",
                    "msg": "未到异步系统开放时间"
                }), 200

        return decorator

    return wrapper


def in_step_3_period():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            start_at = datetime.datetime.strptime(get_system_setting('step_3_start_at'), "%Y-%m-%d %H:%M:%S")
            end_at = datetime.datetime.strptime(get_system_setting('step_3_end_at'), "%Y-%m-%d %H:%M:%S")
            if start_at <= datetime.datetime.now() <= end_at:
                return fn(*args, **kwargs)
            else:
                return jsonify({
                    "code": "400",
                    "msg": "未到舍友双选系统开放时间"
                }), 200

        return decorator

    return wrapper


@student_pages.route('/login', methods=['POST'])
def login():
    if request.json is not None:
        id = request.json.get('id', None)
        password = request.json.get('password', None)
        student = db_session.query(Student).where(Student.id == id).first()
        if student is not None and student.check_password(password):
            student.last_logged_at = datetime.datetime.now()
            db_session.commit()
            token = create_access_token(identity=student.id, additional_headers={
                "role": "student"
            }, additional_claims={
                "role": "student"
            })

            return jsonify({
                "code": 200,
                "msg": "登录成功！",
                "data": {
                    "access_token": token
                }
            })

    return jsonify({
        "code": 401,
        "msg": "ID 或密码错误！"
    })


@student_pages.get("/userinfo")
@student_required()
def userinfo():
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "user": current_user.to_dict(
                only=['id', 'name', 'gender', 'contact', 'team_id', 'team.id', 'team.students.id', 'team.students.name',
                      'has_answered_questionnaire'])
        }
    })


@student_pages.post('/logout')
@student_required()
def logout():
    return jsonify({
        "code": 200,
        "msg": "success"
    })


@student_pages.get('/questionnaire/list')
@student_required()
def questionnaire_list():
    questionnaire_items = db_session.query(QuestionnaireItem).order_by(QuestionnaireItem.index.asc()).all()

    questionnaire_items = [questionnaire_item.to_dict() for questionnaire_item in questionnaire_items]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": questionnaire_items
    })


@student_pages.get('/questionnaire/answer')
@student_required()
def questionnaire_get_answers():
    questionnaire_answers = db_session.query(QuestionnaireAnswer).filter(
        QuestionnaireAnswer.student_id == current_user.id).options(joinedload(QuestionnaireAnswer.item)).all()

    questionnaire_answers = [questionnaire_answer.to_dict(only=['item_id', 'answer', 'weight', 'item']) for
                             questionnaire_answer in questionnaire_answers]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": questionnaire_answers
    })


@student_pages.post('/questionnaire/answer')
@in_step_1_period()
@student_required()
def questionnaire_set_answers():
    if request.json is not None:
        if type(request.json) is not dict:
            return jsonify({
                "code": 400,
                "msg": "问卷答案数据错误"
            })

        # TODO:: 整合到model里进行
        questionnaire_answers = request.json

        exist_answers = db_session.query(QuestionnaireAnswer).filter(
            QuestionnaireAnswer.student_id == current_user.id).all()
        questionnaire_items = db_session.query(QuestionnaireItem).all()
        default_weight = {}
        missed_items = []
        for questionnaire_item in questionnaire_items:
            default_weight[questionnaire_item.id] = questionnaire_item.weight

        bulk_save_models = []
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

            # TODO: 权重范围限制
            # TODO: SQL性能调优
            data_changed = False
            for exist_answer in exist_answers:
                if exist_answer.item_id == key:
                    need_to_create = False
                    if exist_answer.answer != str(value['answer']) or exist_answer.weight != value['weight']:
                        exist_answer.answer = str(value['answer'])
                        exist_answer.weight = value['weight']
                        exist_answer.updated_at = datetime.datetime.now()
                        db_session.commit()

            if need_to_create:
                new_answer = QuestionnaireAnswer(item_id=key, answer=str(value['answer']), student_id=id,
                                                 weight=value['weight'])
                bulk_save_models.append(new_answer)
                data_changed = True

        # 重头戏 存数据

        if data_changed:
            db_session.bulk_save_objects(bulk_save_models)
            db_session.commit()

            # 删除匹配得分
            db_session.query(MatchingScore).where(
                (MatchingScore.to_student_id == current_user.id) | (
                        MatchingScore.from_student_id == current_user.id)).delete()

            db_session.commit()

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@student_pages.get('/team/recommend_teammates')
@student_required()
@in_step_3_period()
def team_recommend_teammates():
    recommend_scores = db_session.query(MatchingScore) \
        .where(MatchingScore.to_student_id == current_user.id) \
        .options(joinedload(MatchingScore.from_student)) \
        .order_by(MatchingScore.score) \
        .all()

    construct_data = []
    added_student_ids = []
    for piece in recommend_scores:
        if piece.from_student.gender != current_user.gender:
            continue
        item = piece.from_student.to_dict(only=['id', 'name', 'contact'])
        # join load 不能执行关联查询 所以在这里手动过滤

        item['score'] = piece.score
        construct_data.append(item)
        added_student_ids.append(item['id'])

    students_with_no_score = db_session.query(Student) \
        .where(Student.gender == current_user.gender) \
        .where(Student.id.not_in(added_student_ids)) \
        .all()

    students_with_no_score = [piece.to_dict(only=['id', 'name', 'contact']) for piece in students_with_no_score]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "students_with_score": construct_data,
            "students_with_no_score": students_with_no_score
        }
    })


# !!important!! 不推荐邀请同学直接进入队伍！！ 这样很可能会忽视队伍里的其他同学 一定要确定每个人的生活习惯都和自己的没有冲突
# !!important!! 这个API主要用于两个都没有入队伍的同学组成新的队伍
@student_pages.post('/team/invite')
@student_required()
@in_step_3_period()
def team_invite():
    if request.json is not None:
        target_student_id = request.json.get('target_student_id')
        team_id = current_user.team_id
        target_student = db_session.query(Student).get(target_student_id)

        if target_student is None:
            return jsonify({
                "code": 404,
                "msg": "学生不存在"
            })

        # 性别校验
        if target_student.gender != current_user.gender:
            return jsonify({
                "code": 400,
                "msg": "不支持男女混寝"
            })

        if target_student.team_id is not None:
            return jsonify({
                "code": 400,
                "msg": "对方已经在其他队伍中了，不能撬墙角"
            })

        if target_student_id == current_user.id:
            return jsonify({
                "code": 400,
                "msg": "不能自己和自己组队"
            })

        if team_id is not None:
            team = db_session.query(Team).get(team_id)
            if team is None:
                return jsonify({
                    "code": 404,
                    "msg": "队伍不存在"
                })
            # 校验性别
            if team.gender != target_student.gender:
                return jsonify({
                    "code": 400,
                    "msg": "不支持男女混寝"
                })

            # 看看满人了没有
            if len(team.students) >= int(get_system_setting('team_max_student_count')):
                return jsonify({
                    "code": 400,
                    "msg": "队伍满人了"
                })

            # 看看有没有重复的邀请函
            similar_invitation_count = db_session.query(TeamInvitation) \
                .filter(TeamInvitation.to_student_id == target_student_id) \
                .filter(TeamInvitation.team_id == team_id) \
                .filter(TeamInvitation.status == 0) \
                .count()

            if similar_invitation_count > 0:
                return jsonify({
                    "code": 400,
                    "msg": "该同学已经收到过加入本队伍的邀请函"
                })

            similar_request_count = db_session.query(TeamRequest) \
                .filter(TeamRequest.team_id == team_id) \
                .filter(TeamRequest.student_id == target_student_id) \
                .filter(TeamRequest.status == 0) \
                .count()

            if similar_request_count > 0:
                return jsonify({
                    "code": 400,
                    "msg": "该同学已经向本队发出过入队申请，请先处理他的申请"
                })
        else:
            similar_invitation_count = db_session.query(TeamInvitation) \
                .filter(TeamInvitation.to_student_id == target_student_id) \
                .filter(TeamInvitation.from_student_id == current_user.id) \
                .filter(TeamInvitation.team_id == team_id) \
                .filter(TeamInvitation.status == 0) \
                .count()

            if similar_invitation_count > 0:
                return jsonify({
                    "code": 400,
                    "msg": "你已经向该同学发出过组队申请了"
                })

        # 生成邀请函
        invitation = TeamInvitation(
            from_student_id=current_user.id,
            to_student_id=target_student_id,
            team_id=team_id
        )
        db_session.add(invitation)
        db_session.commit()

        return ({
            "code": 200,
            "msg": "success",
            "data": {
                "team_invitation_id": invitation.id
            }
        })

    return jsonify({
        "code": 400,
        "msg": "数据校验错误"
    })


# 入队申请
@student_pages.post('/team/request')
@in_step_3_period()
@student_required()
def team_request():
    if request.json is not None:
        team_id = request.json.get('team_id')
        if current_user.team_id is not None:
            return jsonify({
                "code": 400,
                "msg": "你已经在其他队伍中了，请先退出再加入"
            })

        if team_id is not None:
            team = db_session.query(Team).get(team_id)
            if team is None:
                return jsonify({
                    "code": 404,
                    "msg": "队伍不存在"
                })
            # 校验性别
            if team.gender != current_user.gender:
                return jsonify({
                    "code": 400,
                    "msg": "不支持男女混寝"
                })

            # 看看满人了没有
            if len(team.students) >= int(get_system_setting('team_max_student_count')):
                return jsonify({
                    "code": 400,
                    "msg": "队伍满人了"
                })

            # 看看有没有重复的邀请函
            similar_invitation_count = db_session.query(TeamInvitation) \
                .filter(TeamInvitation.to_student_id == current_user.id) \
                .filter(TeamInvitation.team_id == team_id) \
                .filter(TeamInvitation.status == 0) \
                .count()

            if similar_invitation_count > 0:
                return jsonify({
                    "code": 400,
                    "msg": "你已经收到过这个队伍的邀请函了，请先处理邀请函"
                })

            similar_request_count = db_session.query(TeamRequest) \
                .filter(TeamRequest.team_id == team_id) \
                .filter(TeamRequest.student_id == current_user.id) \
                .filter(TeamRequest.status == 0) \
                .count()

            if similar_request_count > 0:
                return jsonify({
                    "code": 400,
                    "msg": "你已经向这个队伍发出过申请了，不能重复申请"
                })

            # 生成申请
            team_request = TeamRequest(team_id=team_id, student_id=current_user.id)
            db_session.add(team_request)
            db_session.commit()

            return jsonify({
                "code": 200,
                "data": {
                    "team_request_id": team_request.id
                }
            })

    return jsonify({
        "code": 400,
        "msg": "数据校验错误"
    })


@student_pages.get('/team/invitations')
@student_required()
def team_invitation_list():
    # 返回自己发出去和收到的组队申请
    team_invitations = db_session \
        .query(TeamInvitation) \
        .filter((TeamInvitation.to_student_id == current_user.id) | (TeamInvitation.from_student_id == current_user.id)) \
        .options(
        joinedload(TeamInvitation.from_student), joinedload(TeamInvitation.to_student), joinedload(TeamInvitation.team)) \
        .order_by(TeamInvitation.id.desc()) \
        .all()

    team_invitations = [team_invitation.to_dict(
        only=['id', 'team_id', 'status', 'reason', 'created_at', 'to_student.name', 'to_student.id',
              'from_student.name', 'from_student.id', 'team.id',
              'team.description']) for
        team_invitation in team_invitations]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "team_invitations": team_invitations
        }
    })


@student_pages.get('/team/requests')
@student_required()
def team_request_list():
    if current_user.team_id is None:
        # 如果没有入队，则返回申请列表

        team_requests = db_session.query(TeamRequest) \
            .filter(TeamRequest.student_id == current_user.id) \
            .options(joinedload(TeamRequest.team), joinedload(TeamRequest.student)) \
            .order_by(TeamRequest.id.desc()) \
            .all()

        team_requests = [team_request.to_dict(
            ['id', 'team_id', 'team.id', 'team.description', 'reason', 'team.students.id', 'team.students.name',
             'status', 'student.id', 'student.name', 'created_at']) for
            team_request in
            team_requests]

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "team_requests": team_requests
            }
        })

    team_requests = db_session \
        .query(TeamRequest) \
        .where(TeamRequest.team_id == current_user.team_id) \
        .options(joinedload(TeamRequest.student)) \
        .options(joinedload(TeamRequest.student)) \
        .order_by(TeamRequest.id.desc()) \
        .all()

    team_requests = [team_request.to_dict(['id', 'status', 'student.id', 'reason', 'student.name', 'created_at']) for
                     team_request
                     in
                     team_requests]

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "team_requests": team_requests
        }
    })


@student_pages.post('/team/invitation/process')
@student_required()
@in_step_3_period()
def team_invitation_process():
    if request.json is not None:
        team_invitation_id = request.json.get("team_invitation_id", None)
        accept = bool(request.json.get("accept"))

        team_invitation = db_session.query(
            TeamInvitation) \
            .options(joinedload(TeamInvitation.from_student),
                     joinedload(TeamInvitation.to_student)) \
            .filter(TeamInvitation.id == team_invitation_id) \
            .first()

        if team_invitation is not None:
            if (team_invitation.to_student_id != current_user.id) \
                    and (team_invitation.from_student_id != current_user.id):
                return jsonify({
                    "code": 403,
                    "msg": "无权操作"
                })

            if team_invitation.status != 0:
                return jsonify({
                    "code": 400,
                    "msg": "该邀请已被处理"
                })

            if not accept and team_invitation.from_student.id == current_user.id:
                team_invitation.status = -2
                team_invitation.reason = "已被{}撤回".format(current_user.name)
                db_session.commit()
                return jsonify({
                    "code": 200,
                    "msg": "success"
                })

            elif not accept:
                team_invitation.status = -1
                team_invitation.reason = "已被{}拒绝".format(current_user.name)
                db_session.commit()
                return jsonify({
                    "code": 200,
                    "msg": "success"
                })
            elif accept and team_invitation.from_student.id == current_user.id:  # 防止自己给自己同意
                return jsonify({
                    "code": 403,
                    "msg": "无权操作"
                })
            else:
                if team_invitation.team is None:
                    # 创建请求的时候已经进行性别校验
                    team = Team(gender=current_user.gender)
                    db_session.add(team)
                    db_session.commit()

                    result = team_invitation.to_student.set_team(team.id)
                    if result is not True:
                        return result
                    result = team_invitation.from_student.set_team(team.id)
                    if result is not True:
                        return result
                    team_invitation.status = 1
                    team_invitation.reason = "已创建新的队伍"
                    db_session.commit()

                    return jsonify({
                        "code": 200,
                        "msg": "success",
                        "data":
                            {
                                "create_team": True,
                                "team_id": team.id
                            }
                    })

                else:
                    result = team_invitation.to_student.set_team(team_invitation.team_id)
                    if result is not True:
                        return result
                    else:
                        team_invitation.to_student.team_id = team_invitation.team_id
                        team_invitation.status = 1
                        team_invitation.reason = None
                        db_session.commit()
                        return jsonify({
                            "code": 200,
                            "msg": "success",
                            "data":
                                {
                                    "create_team": False,
                                    "team_id": team_invitation.team_id
                                }
                        })

        return jsonify({
            "code": 404,
            "msg": "邀请不存在"
        })

    return jsonify({
        "code": 400,
        "msg": "数据校验错误"
    })


@student_pages.post("/team/request/process")
@student_required()
@in_step_3_period()
def team_request_process():
    if request.json is not None:
        team_request_id = request.json.get("team_request_id", None)
        accept = bool(request.json.get("accept"))

        team_request = db_session.query(TeamRequest) \
            .join(TeamRequest.student, TeamRequest.team) \
            .filter(TeamRequest.id == team_request_id) \
            .first()

        if team_request is not None:
            # 进行一大堆校验
            if (team_request.team_id != current_user.team_id \
                and team_request.student_id != current_user.id) \
                    or (accept and team_request.student.id == current_user.id):  # 防止自己给自己同意
                return jsonify({
                    "code": 403,
                    "msg": "无权操作"
                })

            if team_request.status != 0:
                return jsonify({
                    "code": 400,
                    "msg": "该请求已被处理"
                })

            if not accept and team_request.student.id == current_user.id:
                team_request.status = -2
                team_request.reason = "已被{}撤回".format(current_user.name)
                db_session.commit()
                return jsonify({
                    "code": 200,
                    "msg": "success"
                })
            elif not accept:
                team_request.status = -1
                team_request.reason = "已被{}拒绝".format(current_user.name)
                db_session.commit()
                return jsonify({
                    "code": 200,
                    "msg": "success"
                })
            else:
                result = team_request.student.set_team(team_request.team_id)

                if result is True:
                    team_request.status = 1
                    team_request.reason = "已被{}接受".format(current_user.name)
                    db_session.commit()

                    return jsonify({
                        "code": 200,
                        "msg": "success"
                    })
                else:
                    return result

        return jsonify({
            "code": 404,
            "msg": "请求不存在"
        })

    return jsonify({
        "code": 400,
        "msg": "数据校验错误"
    })


@student_pages.get("/system_setting")
@student_required()
def get_system_settings():
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "step_1_start_at": get_system_setting("step_1_start_at"),
            "step_1_end_at": get_system_setting("step_1_end_at"),
            "step_2_start_at": get_system_setting("step_2_start_at"),
            "step_2_end_at": get_system_setting("step_2_end_at"),
            "step_3_start_at": get_system_setting("step_3_start_at"),
            "step_3_end_at": get_system_setting("step_3_end_at"),
            "team_max_student_count": get_system_setting("team_max_student_count"),
            "questionnaire_json": get_system_setting("questionnaire_json", {})
        }
    })


@student_pages.get("/student/<int:id>")
@student_required()
def get_student_detail(id):
    # TODO:: 优化Questionnaire_item的 SQL
    student = db_session.query(Student).filter(Student.id == id) \
        .join(Team, QuestionnaireAnswer,
              isouter=True) \
        .first()

    matching_score = db_session.query(MatchingScore) \
        .filter(MatchingScore.from_student_id == student.id) \
        .filter(MatchingScore.to_student_id == current_user.id) \
        .first()

    if matching_score is not None:
        student.score = matching_score.score
    else:
        student.score = None

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": student.to_dict(
            only=['id', 'name', 'team', 'team_id', 'score', 'questionnaire_answers', 'contact', 'team.id',
                  'team.students.id',
                  'team.students.name', 'team.students.contact', 'has_answered_questionnaire'])
    })


@student_pages.get("/team/detail")
@student_required()
def get_team_detail():
    if current_user.team is None:
        return jsonify({
            "code": 400,
            "msg": "你还没有加入任何队伍"
        })
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": current_user.team.to_dict(['id', 'description', 'students.id',
                                           'students.name', 'students.contact', 'students.has_answered_questionnaire',
                                           'students.questionnaire_answers'])
    })


@student_pages.post("/team/quit")
@student_required()
def quit_team():
    if current_user.team is None:
        return jsonify({
            "code": 400,
            "msg": "你还没有加入任何队伍"
        })

    result = current_user.set_team(None)
    if result is not True:
        return result

    return jsonify({
        "code": 200,
        "msg": "success"
    })


@student_pages.post("/change_password")
@student_required()
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


@student_pages.post("/update_contact")
@student_required()
def update_contact():
    if request.json is not None:
        new_contact = request.json.get("contact")
        if new_contact is None:
            return jsonify({
                "code": 400,
                "msg": "联系方式不能为空"
            })

        current_user.contact = new_contact
        db_session.commit()
        return jsonify({
            "code": 200,
            "msg": "success"
        })

    else:
        return jsonify({
            "code": 400,
            "msg": "数据校验错误"
        })
