# Unicorn Startup Ecosystem Analysis

## Project Overview
This project simulates an End-to-End ETL (Extract, Transform, Load) process and data analysis workflow focusing on the global unicorn startup landscape. 

Due to the limited availability of comprehensive open-source unicorn databases, this project utilizes Python to programmatically generate a highly realistic relational dataset. The generated data is then loaded into an in-memory SQLite database, allowing for robust data extraction and aggregation using SQL, followed by data visualization to uncover actionable business insights.

## Key Skills Demonstrated
* **Data Engineering (ETL):** Designed a data generation pipeline using `Faker` and `NumPy` vectorization to create thousands of data points efficiently. 
* **Database Management:** Modeled relational data (Companies, Industries, Funding, Dates) and integrated it with an SQLite RDBMS.
* **SQL Querying:** Extracted and aggregated data using complex SQL `JOIN`, `GROUP BY`, and mathematical operations.
* **Data Visualization:** Translated raw data into clean, business-ready charts using `Seaborn` and `Matplotlib`.

## Tech Stack
* **Language:** Python 3.10
* **Database:** SQLite (In-Memory)
* **Libraries:** Pandas, NumPy, Faker, Matplotlib, Seaborn

## Business Questions Answered
Through SQL queries and visual analysis, this notebook answers three core business questions:
1. **Industry Dominance:** Which industries produce the highest number of unicorn startups?
2. **Top Valuations:** Which 5 companies have the highest valuations, and where are they geographically located?
3. **Historical Trends:** How has the number of newly crowned unicorns grown over the years?

## Project Structure
* `unicorn_analysis.ipynb`: The main Jupyter Notebook containing the ETL pipeline, SQL queries, and visualizations.
* `environment.yml`: Conda environment configuration file to reproduce the exact dependencies used in this project.
* `.gitignore`: Configured to ignore auto-generated dummy CSV files and local cache.

## How to Run This Project
To replicate the environment and run the notebook locally, follow these steps:

1. Clone this repository:
   ```bash
   git clone [https://github.com/subki72/unicorn-startup-analysis.git](https://github.com/subki72/unicorn-startup-analysis.git)
   cd unicorn-startup-analysis

```

2. Create the conda environment from the provided configuration file:
```bash
conda env create -f environment.yml

```


3. Activate the environment:
```bash
conda activate unicorn_env

```


4. Launch Jupyter Notebook:
```bash
jupyter notebook

```