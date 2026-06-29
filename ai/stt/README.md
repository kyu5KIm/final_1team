# STT Service

회의 녹음 파일을 텍스트로 변환하는 FastAPI 서버입니다. WhisperX를 사용하며, 옵션에 따라 align과 diarization을 적용할 수 있습니다.

## 역할

- `webm`, `wav`, `mp3` 등 음성 파일을 업로드 받아 텍스트로 변환
- 참석자 목록을 받아 transcript 상단에 포함
- segment 단위 speaker/time/text 구조 생성
- 긴 STT 작업을 위한 비동기 job API 제공

## 주요 파일

| 파일 | 설명 |
| --- | --- |
| `stt_server.py` | FastAPI 앱, STT API, job 관리 |
| `config.py` | WhisperX 모델, device, batch, align/diarize 설정 |
| `model_runtime.py` | WhisperX 모델 로딩과 실제 transcribe 로직 |
| `schemas.py` | 공통 요청/응답 모델 |
| `requirements-stt.txt` | STT 서버 의존성 |

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 서버 상태, STT 모델, CUDA 여부 확인 |
| `POST` | `/stt` | 음성 파일을 바로 텍스트로 변환 |
| `POST` | `/transcribe` | `/stt`와 동일한 별칭 |
| `POST` | `/stt/jobs` | STT job 생성 |
| `POST` | `/transcribe/jobs` | STT job 생성 별칭 |
| `GET` | `/stt/jobs/{job_id}` | STT job 상태/결과 조회 |
| `GET` | `/transcribe/jobs/{job_id}` | STT job 상태/결과 조회 별칭 |

## 실행 방법

```bash
cd ai/stt
pip install -r requirements-stt.txt
uvicorn stt_server:app --host 0.0.0.0 --port 8502 --reload
```

## 주요 환경변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `STT_MODEL_ID` | `large-v3` | WhisperX/Whisper 모델 |
| `STT_DEVICE` | `cuda` | 실행 device |
| `STT_COMPUTE_TYPE` | `float16` | 연산 타입 |
| `STT_BATCH_SIZE` | `16` | STT batch size |
| `STT_PRELOAD_MODEL` | `false` | 서버 시작 시 모델 선로딩 여부 |
| `STT_ENABLE_ALIGN` | `true` | 단어/문장 alignment 사용 여부 |
| `STT_ENABLE_DIARIZE` | `false` | 화자 분리 사용 여부 |
| `STT_JOB_WORKERS` | `1` | job worker 수 |
| `HF_TOKEN` | 없음 | diarization 또는 Hugging Face 모델 접근에 사용 |

## .env 양식

`ai/stt/.env` 예시입니다.

```dotenv
# WhisperX model
STT_MODEL_ID=large-v3
STT_DEVICE=cuda
STT_COMPUTE_TYPE=float16
STT_BATCH_SIZE=16
STT_PRELOAD_MODEL=false

# Alignment / diarization
STT_ENABLE_ALIGN=true
STT_ENABLE_DIARIZE=false

# Job worker
STT_JOB_WORKERS=1

# Diarization 또는 private model 접근에 필요할 수 있음
HF_TOKEN=
HF_HUB_ENABLE_HF_TRANSFER=1
```

## 요청 파라미터

`/stt`, `/transcribe`, `/stt/jobs`는 multipart form 요청을 받습니다.

| 필드 | 기본값 | 설명 |
| --- | --- | --- |
| `file` | 필수 | 음성 파일 |
| `language` | `ko` | 음성 언어 |
| `align` | 환경변수 기본값 | alignment 적용 여부 |
| `diarize` | 환경변수 기본값 | 화자 분리 적용 여부 |
| `batch_size` | 환경변수 기본값 | STT batch size |
| `participants` | 빈 문자열 | 쉼표로 구분한 참석자 이름 |

## 요청 예시

```bash
curl -X POST "http://localhost:8502/stt" \
  -F "file=@meeting.webm" \
  -F "language=ko" \
  -F "participants=김철수,이영희"
```

비동기 job 방식:

```bash
curl -X POST "http://localhost:8502/stt/jobs" \
  -F "file=@meeting.webm" \
  -F "language=ko"

curl "http://localhost:8502/stt/jobs/{job_id}"
```

## 결과 형태

동기 API는 plain text transcript를 반환합니다. 내부 job 결과에는 대략 다음 구조가 들어갑니다.

```json
{
  "text": "[참석자]\n- ...\n\n[발화 원문]\n[00:01] SPEAKER_00: ...",
  "segments": [
    {
      "speaker": "SPEAKER_00",
      "time": "[00:01]",
      "start": 1.2,
      "end": 4.5,
      "text": "발화 내용"
    }
  ]
}
```

## 백엔드 연동

Django 백엔드는 회의 종료 또는 녹음 처리 단계에서 `RUNPOD_STT_BASE_URL`로 이 서버를 호출합니다.

```text
RUNPOD_STT_BASE_URL=http://localhost:8502
```

## 주의사항

- diarization은 `HF_TOKEN`과 추가 모델 접근 권한이 필요할 수 있습니다.
- 긴 회의 녹음은 job API를 사용하는 것이 안정적입니다.
- GPU 메모리가 부족하면 batch size를 낮춥니다.
- 업로드된 녹음 파일과 `.env`는 Git에 올리지 않습니다.
