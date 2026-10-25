.PHONY: api worker

api:
	uvicorn app.main:app --reload

worker:
	arq app.services.worker.worker.WorkerSettings
