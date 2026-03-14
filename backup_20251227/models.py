from flask_sqlalchemy import SQLAlchemy
from flask_security import UserMixin, RoleMixin
import uuid
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
import warnings

warnings.filterwarnings("ignore")

db = SQLAlchemy()

# User와 Role 관계 = Many-to-Many
user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(20), nullable=False)
    birth = db.Column(db.Date, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    roles = db.relationship('Role', secondary=user_roles, backref='users')


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cctv_name = db.Column(db.String(255), unique=True, nullable=False)
    lng = db.Column(db.String(50), nullable=False)  # 충분한 길이를 확보합니다.
    lat = db.Column(db.String(50), nullable=False)


class TrafficStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Location 테이블의 id를 참조하는 Foreign Key (1:N 관계의 N쪽)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    # 분석 시점 (어떤 시점의 데이터인지 기록)
    timestamp = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    # 상행선 (서울 방향) 상태: 원활, 서행, 정체, N/A
    status_upstream = db.Column(db.String(50), nullable=False)
    # 하행선 (부산 방향) 상태: 원활, 서행, 정체, N/A
    status_downstream = db.Column(db.String(50), nullable=False)

    location = db.relationship(
        'Location',
        backref=db.backref('statuses', lazy='dynamic', order_by=timestamp.desc())
    )


# ============================================================
# 교통량 예측 모델 (독립된 클래스)
# ============================================================
class TrafficPredictor:
    """교통량 예측 모델"""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.features = None
        self.section = None
        self.history = None

    def load_data(self, df, section):
        """특정 구간 데이터 로드"""
        self.section = section

        df['ds'] = pd.to_datetime(df['일시'])
        df['y'] = df['교통량']

        df_sec = (
            df[df['구간'] == section]
            .sort_values('ds')
            .reset_index(drop=True)
        )

        return df_sec

    def engineer_features(self, df_sec):
        """Feature Engineering"""
        df_sec = df_sec.copy()

        df_sec['요일'] = df_sec['ds'].dt.dayofweek
        df_sec['시간'] = df_sec['ds'].dt.hour
        df_sec['일'] = df_sec['ds'].dt.day
        df_sec['월'] = df_sec['ds'].dt.month
        df_sec['주'] = df_sec['ds'].dt.isocalendar().week.astype(int)

        for l in self.config.LAG_LIST:
            df_sec[f'lag_{l}'] = df_sec['y'].shift(l)

        df_sec['roll_24'] = df_sec['y'].rolling(24).mean()
        df_sec['roll_168'] = df_sec['y'].rolling(168).mean()

        self.features = (
                [f'lag_{l}' for l in self.config.LAG_LIST] +
                ['roll_24', 'roll_168', '요일', '시간', '일', '월', '주']
        )

        df_sec = df_sec.dropna().reset_index(drop=True)
        return df_sec

    def train(self, df_sec):
        """모델 학습"""
        train_end = pd.Timestamp(self.config.TRAIN_END)
        valid_end = pd.Timestamp(self.config.VALID_END)

        train = df_sec[df_sec['ds'] <= train_end]
        valid = df_sec[(df_sec['ds'] > train_end) & (df_sec['ds'] <= valid_end)]

        if len(valid) == 0:
            train_end = df_sec['ds'].quantile(0.85)
            valid = df_sec[df_sec['ds'] > train_end]
            train = df_sec[df_sec['ds'] <= train_end]

        X_train, y_train = train[self.features], train['y']
        X_valid, y_valid = valid[self.features], valid['y']

        self.model = XGBRegressor(**self.config.XGBOOST_PARAMS)
        self.model.fit(X_train, y_train)

        self.history = df_sec.set_index('ds')['y'].copy()

        metrics = None
        if len(valid) > 0:
            valid = valid.copy()
            valid['pred'] = self.model.predict(X_valid)

            metrics = {
                'mae': float(mean_absolute_error(y_valid, valid['pred'])),
                'mape': float(mean_absolute_percentage_error(y_valid, valid['pred']) * 100),
                'r2': float(r2_score(y_valid, valid['pred'])),
                'train_size': len(train),
                'valid_size': len(valid)
            }

        return metrics

    def predict_future(self, start_date, end_date):
        """미래 예측"""
        if self.model is None:
            raise ValueError("모델이 학습되지 않았습니다.")

        future_dates = pd.date_range(start=start_date, end=end_date, freq='H')
        history = self.history.copy()
        preds = []

        for t in future_dates:
            row = {
                '요일': t.dayofweek,
                '시간': t.hour,
                '일': t.day,
                '월': t.month,
                '주': t.isocalendar().week
            }

            for l in self.config.LAG_LIST:
                row[f'lag_{l}'] = history.iloc[-l]

            row['roll_24'] = history.iloc[-24:].mean()
            row['roll_168'] = history.iloc[-168:].mean()

            X = pd.DataFrame([row])[self.features]
            y_hat = self.model.predict(X)[0]
            y_hat = max(0, y_hat)

            preds.append(y_hat)
            history.loc[t] = y_hat

        return pd.DataFrame({
            'ds': future_dates,
            'pred': preds
        })