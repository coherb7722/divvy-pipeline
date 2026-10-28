.PHONY: install sample run test dashboard docker clean

install:      ## install Python dependencies
	pip install -r requirements.txt

sample:       ## run the full pipeline on generated sample data (no internet)
	python -m pipeline.run --sample

run:          ## run the full pipeline on real Divvy + weather data
	python -m pipeline.run

test:         ## unit tests
	pytest -q

dashboard:    ## open the dashboard at http://localhost:8501
	streamlit run dashboard/app.py

docker:       ## run pipeline + dashboard in containers
	docker compose up --build

clean:        ## delete all data and dbt build output
	rm -rf data divvy_dbt/target divvy_dbt/logs logs
