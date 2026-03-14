from flask import Blueprint, request, jsonify, render_template  # ty:ignore[unresolved-import]
import pandas as pd
from mp.models import TrafficPredictor
from config import Config

bp = Blueprint('traffic_predict', __name__, url_prefix='/traffic_predict')

# 전역 캐시
_df_cache = None
_models_cache = {}


def load_dataframe():
    """데이터 로드 (캐싱)"""
    global _df_cache
    if _df_cache is None:
        try:
            _df_cache = pd.read_csv(Config.DATA_PATH)
        except FileNotFoundError:
            raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {Config.DATA_PATH}")
    return _df_cache


# ============================================================
# 🌐 웹페이지 라우트
# ============================================================

@bp.route('/')
def traffic_page():
    """교통량 예측 메인 페이지"""
    try:
        return render_template('traffic_predict.html')
    except:
        # traffic.html이 없으면 JSON 응답
        return jsonify({
            'message': '교통량 예측 API',
            'endpoints': {
                'sections': '/traffic/api/sections',
                'predict': '/traffic/api/predict'
            }
        })


# ============================================================
# 🔌 API 라우트
# ============================================================

@bp.route('/api/sections', methods=['GET'])
def get_sections():
    """구간 목록 조회 API"""
    try:
        df = load_dataframe()
        sections = df['구간'].unique().tolist()

        return jsonify({
            'success': True,
            'sections': sections,
            'count': len(sections)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/predict', methods=['POST'])
def predict_traffic():
    """교통량 예측 API"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'JSON 데이터가 필요합니다.'
            }), 400

        section_name = data.get('section')
        start_date = data.get('start_date', '2025-12-01 00:00:00')
        end_date = data.get('end_date', '2025-12-31 23:00:00')

        if not section_name:
            return jsonify({
                'success': False,
                'error': '구간을 선택해주세요.'
            }), 400

        # 모델 캐시 확인
        if section_name not in _models_cache:
            df = load_dataframe()

            # 구간 존재 여부 확인
            if section_name not in df['구간'].values:
                return jsonify({
                    'success': False,
                    'error': f'구간을 찾을 수 없습니다: {section_name}'
                }), 404

            print(f"[INFO] {section_name} 구간 모델 학습 시작...")

            predictor = TrafficPredictor(Config)
            df_sec = predictor.load_data(df, section_name)
            df_sec = predictor.engineer_features(df_sec)
            metrics = predictor.train(df_sec)

            _models_cache[section_name] = {
                'predictor': predictor,
                'metrics': metrics
            }

            print(f"[INFO] {section_name} 구간 모델 학습 완료!")

        # 예측 수행
        print(f"[INFO] {section_name} 구간 예측 시작...")
        predictor = _models_cache[section_name]['predictor']
        pred_df = predictor.predict_future(start_date, end_date)

        # 통계 계산
        stats = {
            'mean': float(pred_df['pred'].mean()),
            'max': float(pred_df['pred'].max()),
            'min': float(pred_df['pred'].min()),
            'std': float(pred_df['pred'].std())
        }

        print(f"[INFO] {section_name} 구간 예측 완료! (총 {len(pred_df)}개 시간)")

        return jsonify({
            'success': True,
            'section': section_name,
            'metrics': _models_cache[section_name]['metrics'],
            'statistics': stats,
            'prediction_count': len(pred_df),
            'predictions': pred_df.to_dict('records')
        })

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 예측 중 오류 발생:\n{error_detail}")

        return jsonify({
            'success': False,
            'error': str(e),
            'detail': error_detail
        }), 500


@bp.route('/api/status', methods=['GET'])
def get_status():
    """캐시 상태 확인"""
    return jsonify({
        'success': True,
        'cached_sections': list(_models_cache.keys()),
        'cache_count': len(_models_cache),
        'data_loaded': _df_cache is not None
    })