# coding: utf-8
from copy import deepcopy

import bcrypt
from flask import jsonify
from sqlalchemy import Column, DateTime, ForeignKey, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT, DOUBLE
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_serializer import SerializerMixin

from database import db_session

Base = declarative_base()


class Admin(Base, SerializerMixin):
    __tablename__ = 'admins'

    id = Column(INTEGER(11), primary_key=True)
    username = Column(String(32), nullable=False)
    email = Column(String(128), nullable=False, unique=True)
    password = Column(String(128))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    last_logged_at = Column(DateTime)

    def check_password(self, password):
        return bcrypt.checkpw(bytes(password, encoding='utf8'), bytes(self.password, encoding='utf8'))


class QuestionnaireItem(Base, SerializerMixin):
    __tablename__ = 'questionnaire_items'

    id = Column(String(128), primary_key=True)
    title = Column(Text, nullable=False)
    weight = Column(DOUBLE(), nullable=False, server_default=text("'1'"))
    data_type = Column(String(32), server_default=text("'integer'"))
    params = Column(Text)
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    index = Column(INTEGER(11), server_default=text("'1'"))
    type = Column(String(64), nullable=False, server_default=text("'text'"))


class SystemSetting(Base, SerializerMixin):
    __tablename__ = 'system_settings'

    id = Column(INTEGER(11), primary_key=True)
    key = Column(String(255), nullable=False, unique=True)
    value = Column(Text)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Team(Base, SerializerMixin):
    __tablename__ = 'teams'

    id = Column(INTEGER(11), primary_key=True)
    gender = Column(TINYINT(4), comment='男1 女2')
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    team_requests = relationship("TeamRequest", backref="team", cascade='all, delete-orphan',
                                 passive_deletes=True)
    students = relationship('Student', backref="team")

    serialize_rules = ('-students.team',)


class Student(Base, SerializerMixin):
    __tablename__ = 'students'

    id = Column(BIGINT(20), primary_key=True)
    team_id = Column(ForeignKey('teams.id', ondelete='SET NULL', onupdate='CASCADE'), index=True)
    gender = Column(TINYINT(4), comment='男1 女2')
    contact = Column(Text)
    password = Column(String(128), nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    last_logged_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    name = Column(String(64), nullable=False)
    QQ = Column(Text)
    Wechat = Column(Text)
    Phone = Column(Text)
    mbti = Column(String(4))

    custom_questionnaire_items = relationship('CustomQuestionnaireItem', backref="student")
    custom_questionnaire_answers = relationship('CustomQuestionnaireAnswer', backref="student")
    questionnaire_answers = relationship('QuestionnaireAnswer', backref="student")
    exchanging_need = relationship('ExchangingNeed', backref="student", cascade='all, delete-orphan',
                                   passive_deletes=True)
    sent_exchanging_requests = relationship('ExchangingRequest',
                                            primaryjoin='ExchangingRequest.from_student_id == Student.id',
                                            backref="from_student", cascade='all, delete-orphan',
                                            passive_deletes=True)
    received_exchanging_requests = relationship('ExchangingRequest',
                                                primaryjoin='ExchangingRequest.to_student_id == Student.id',
                                                backref="to_student")
    team_requests = relationship("TeamRequest", backref="student", cascade='all, delete-orphan',
                                 passive_deletes=True)

    sent_team_invitations = relationship('TeamInvitation', backref="from_student",
                                         primaryjoin='TeamInvitation.from_student_id == Student.id',
                                         cascade='all, delete-orphan',
                                         passive_deletes=True)
    received_team_invitations = relationship('TeamInvitation', backref="to_student",
                                             primaryjoin='TeamInvitation.to_student_id == Student.id')

    serialize_rules = ('-team.students', '-custom_questionnaire_items.student', '-questionnaire_answers.student',
                       '-exchanging_need.student', '-sent_exchanging_requests.student',
                       '-received_exchanging_requests.student',
                       '-custom_questionnaire_answers',
                       '-sent_matching_scores',
                       '-sent_exchanging_requests')

    def check_password(self, password):
        return bcrypt.checkpw(bytes(password, encoding='utf8'), bytes(self.password, encoding='utf8'))

    # 给学生设置队伍
    # Attention: 若非退出队伍操作，该项操作过后，与该学生所有有关的组队申请均会无效，若队伍满员，则与该队伍所有有关的入队申请均会无效
    # Attention: 若为退出队伍操作，且队伍人数为两人，则退出队伍后该队伍将会被解散
    def set_team(self, team_id, delete_team=True, invalidate_requests=True, invalidate_invitations=True,
                 lock_team_if_full=True):
        if team_id is None:
            # 进行一大堆复杂的校验
            if self.team_id is None:
                return True

            if len(self.team.students) <= 2 and delete_team:
                team = deepcopy(self.team)
                for item in self.team.students:
                    item.team_id = None
                db_session.bulk_save_objects(self.team.students)
                db_session.commit()

                db_session.query(TeamInvitation) \
                    .filter(TeamInvitation.status == 0) \
                    .filter(TeamInvitation.team_id == team_id) \
                    .update({
                    TeamInvitation.status: -2,
                    TeamInvitation.team_id: None,
                    TeamInvitation.reason: "目标队伍因人数太少而解散，请求失效"
                })

                db_session.query(TeamRequest) \
                    .filter(TeamRequest.status == 0) \
                    .filter(TeamRequest.team_id == team_id).update({
                    TeamRequest.status: -2,
                    TeamRequest.team_id: None,
                    TeamRequest.reason: "目标队伍因人数太少而解散，请求失效"
                })

                db_session.commit()

                db_session.delete(team)
                db_session.commit()
            else:
                self.team_id = None
                db_session.commit()

            return True
        else:
            # 进行一大堆复杂的校验
            if self.team_id is not None:

                if self.team_id is team_id:
                    return True
                #
                # return jsonify({
                #     "code": 400,
                #     "msg": "学生已经在其他队伍中，请先退出再加入"
                # })
            team = db_session.query(Team).get(team_id)
            if team is None:
                return jsonify({
                    "code": 404,
                    "msg": "队伍不存在"
                })
            elif int(team.gender) != int(self.gender):
                return jsonify({
                    "code": 400,
                    "msg": "性别不同，不能男女混寝"
                })
            students_count_in_team = db_session.query(Student).where(Student.team_id == team_id).count()
            team_is_nearly_full = False
            if int(students_count_in_team) >= int(get_system_setting("team_max_student_count", 4)):
                return jsonify({
                    "code": 400,
                    "msg": "该队伍人数已满"
                })
            elif int(students_count_in_team) == (int(get_system_setting("team_max_student_count", 4)) - 1):
                team_is_nearly_full = True

            # 校验结束
            if self.team_id is not None:
                self.set_team(None)

            self.team_id = team_id
            db_session.commit()

            # 使其他队伍请求无效
            if invalidate_invitations:
                db_session.query(TeamInvitation) \
                    .filter(TeamInvitation.status == 0) \
                    .filter(TeamInvitation.from_student_id == self.id) \
                    .update({
                    TeamInvitation.status: -2,
                    TeamInvitation.reason: "请求发出者已加入其他队伍，请求无效"
                })

                db_session.query(TeamInvitation) \
                    .filter(TeamInvitation.status == 0) \
                    .filter(TeamInvitation.to_student_id == self.id) \
                    .update({
                    TeamInvitation.status: -2,
                    TeamInvitation.reason: "被邀请者已加入其他队伍，请求无效"
                })

            if invalidate_requests:
                db_session.query(TeamRequest) \
                    .filter(TeamRequest.status == 0) \
                    .filter(TeamRequest.student_id == self.id).update({
                    TeamRequest.status: -2,
                    TeamRequest.reason: "已进入其他队伍，请求失效"
                })

            if team_is_nearly_full and lock_team_if_full:
                db_session.query(TeamInvitation) \
                    .filter(TeamInvitation.status == 0) \
                    .filter(TeamInvitation.team_id == team_id) \
                    .update({
                    TeamInvitation.status: -2,
                    TeamInvitation.reason: "目标队伍已满人，请求失效"
                })

                db_session.query(TeamRequest) \
                    .filter(TeamRequest.status == 0) \
                    .filter(TeamRequest.team_id == team_id).update({
                    TeamRequest.status: -2,
                    TeamRequest.reason: "目标队伍已满人，请求失效"
                })

            db_session.commit()

            return True

    def has_answered_questionnaire(self):
        return len(self.questionnaire_answers) > 0


class CustomQuestionnaireItem(Base, SerializerMixin):
    __tablename__ = 'custom_questionnaire_items'

    id = Column(INTEGER(11), primary_key=True)
    student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    type = Column(String(64))
    title = Column(Text)
    params = Column(Text)
    index = Column(INTEGER(11), server_default=text("'1'"))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class CustomQuestionnaireAnswer(Base, SerializerMixin):
    __tablename__ = 'custom_questionnaire_answers'

    id = Column(INTEGER(11), primary_key=True)
    item_id = Column(INTEGER(11))
    answer = Column(Text)
    student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ExchangingNeed(Base, SerializerMixin):
    __tablename__ = 'exchanging_needs'

    id = Column(INTEGER(11), primary_key=True)
    student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    reason = Column(Text)
    expectation = Column(Text)
    processed = Column(TINYINT(1), server_default=text("'0'"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ExchangingRequest(Base, SerializerMixin):
    __tablename__ = 'exchanging_requests'

    id = Column(INTEGER(11), primary_key=True)
    status = Column(TINYINT(4), server_default=text("'0'"), comment='0未处理 -1拒绝 1通过')
    to_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    from_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


class MatchingScore(Base, SerializerMixin):
    __tablename__ = 'matching_scores'

    id = Column(INTEGER(11), primary_key=True)
    from_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False,
                             index=True)
    to_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False,
                           index=True)
    score = Column(INTEGER(11), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    from_student = relationship('Student', primaryjoin='MatchingScore.from_student_id == Student.id', cascade = "all,delete",
                                backref="sent_matching_scores")
    to_student = relationship('Student', primaryjoin='MatchingScore.to_student_id == Student.id', cascade = "all,delete",
                              backref="received_matching_scores")


class QuestionnaireAnswer(Base, SerializerMixin):
    __tablename__ = 'questionnaire_answers'

    id = Column(INTEGER(11), primary_key=True)
    item_id = Column(ForeignKey('questionnaire_items.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    answer = Column(Text)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    weight = Column(DOUBLE(), nullable=False, server_default=text("'1'"))
    
    item = relationship('QuestionnaireItem', order_by="asc(QuestionnaireItem.index)",
                        primaryjoin='QuestionnaireItem.id == QuestionnaireAnswer.item_id', lazy='joined')


class TeamRequest(Base, SerializerMixin):
    __tablename__ = 'team_requests'

    id = Column(INTEGER(11), primary_key=True)
    status = Column(TINYINT(4), server_default=text("'0'"), comment='0未处理 -1拒绝 1通过\\n')
    team_id = Column(ForeignKey('teams.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    reason = Column(Text)
    student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    serialize_rules = ['-student', '-team']


class TeamInvitation(Base, SerializerMixin):
    __tablename__ = 'team_invitations'

    id = Column(INTEGER(11), primary_key=True)
    team_id = Column(ForeignKey('teams.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    from_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    to_student_id = Column(ForeignKey('students.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    status = Column(TINYINT(4), server_default=text("'0'"), comment='0未处理 -1拒绝  -2无效 1通过')
    reason = Column(Text)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    team = relationship('Team')


def get_system_setting(key, default=None):
    item = db_session.query(SystemSetting.value).where(SystemSetting.key == key).first()

    if item is None:
        return default
    else:
        return item.value


def set_system_setting(key, value):
    item = db_session.query(SystemSetting.value).where(SystemSetting.key == key).first()

    if item is None:
        item = SystemSetting(key=key, value=value)
        db_session.add(item)
        db_session.commit()

    else:
        item.value = value
        db_session.commit()


if __name__ == "__main__":
    from database import engine
    Base.metadata.create_all(engine)
