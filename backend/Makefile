deploy:
	python -m app.management.deploy_setup

seed:
	python -m app.management.seed_inicial

run-backend:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	streamlit run app.py --server.port 8501 --server.address 0.0.0.0
