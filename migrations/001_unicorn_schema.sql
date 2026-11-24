-- Migration 001: Normalized Relational Schema for Unicorn Startup Ecosystem
-- Mirrors and formalizes the 4-table RDBMS model from Unicorn_Analysis.ipynb

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS unicorn_companies (
    company_id INTEGER PRIMARY KEY CHECK (company_id >= 1),
    company TEXT NOT NULL CHECK (length(trim(company)) > 0),
    city TEXT NOT NULL CHECK (length(trim(city)) > 0),
    country TEXT NOT NULL CHECK (length(trim(country)) > 0),
    continent TEXT NOT NULL CHECK (length(trim(continent)) > 0)
);

CREATE TABLE IF NOT EXISTS unicorn_industries (
    company_id INTEGER PRIMARY KEY,
    industry TEXT NOT NULL CHECK (length(trim(industry)) > 0),
    FOREIGN KEY (company_id) REFERENCES unicorn_companies (company_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unicorn_funding (
    company_id INTEGER PRIMARY KEY,
    valuation INTEGER NOT NULL CHECK (valuation > 0),
    funding INTEGER NOT NULL CHECK (funding > 0),
    select_investors TEXT NOT NULL CHECK (length(trim(select_investors)) > 0),
    FOREIGN KEY (company_id) REFERENCES unicorn_companies (company_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unicorn_dates (
    company_id INTEGER PRIMARY KEY,
    date_joined TEXT NOT NULL CHECK (length(date_joined) = 10),
    year_founded INTEGER NOT NULL CHECK (year_founded >= 1900 AND year_founded <= 2100),
    FOREIGN KEY (company_id) REFERENCES unicorn_companies (company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_unicorn_industries_industry
    ON unicorn_industries (industry);

CREATE INDEX IF NOT EXISTS idx_unicorn_funding_valuation
    ON unicorn_funding (valuation DESC);

CREATE INDEX IF NOT EXISTS idx_unicorn_dates_date_joined
    ON unicorn_dates (date_joined);
