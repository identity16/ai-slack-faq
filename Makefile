.PHONY: setup install run clean env-setup env-copy lint

# 가상환경 이름
VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# 기본 명령어
help:
	@echo "사용 가능한 명령어:"
	@echo "  make setup      - 가상환경 생성 및 패키지 설치"
	@echo "  make install    - 패키지 설치"
	@echo "  make run        - 프로그램 실행"
	@echo "  make clean      - 가상환경 및 캐시 파일 삭제"
	@echo "  make env-setup  - .env 파일 설정"
	@echo "  make env-copy   - .env.example을 .env로 복사"
	@echo "  make lint       - 코드 린팅"

# 가상환경 설정 및 패키지 설치
setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# 패키지만 설치
install:
	$(PIP) install -r requirements.txt

# 프로그램 실행
run:
	PYTHONPATH=$(VENV)/lib/python3.11/site-packages \
	$(PYTHON) -m streamlit run playground.py

# 청소
clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".DS_Store" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.egg" -delete

# .env 파일 설정
env-setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env 파일이 생성되었습니다. API 키를 설정해주세요."; \
	else \
		echo ".env 파일이 이미 존재합니다."; \
	fi

# .env.example을 .env로 복사
env-copy:
	cp .env.example .env
	@echo ".env.example을 .env로 복사했습니다. API 키를 설정해주세요."

# 린팅
lint:
	$(PIP) install pylint
	$(VENV)/bin/pylint playground.py 