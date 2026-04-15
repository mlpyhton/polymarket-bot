# Polymarket Trading Bot

Prototype trading system for prediction markets.

## Overview
This project explores building a systematic trading strategy by comparing model probabilities to market prices and executing trades based on edge. This repository includes both the core simulation framework and exploratory components (data pipelines, edge modeling, and preprocessing modules) reflecting ongoing research.

## Architecture
- Signal generation (model vs market)
- Execution simulation (bid/ask + slippage)
- Risk management (position limits)
- Portfolio tracking (PnL, drawdown)
- Logging and analysis

## Status
Work in progress.

- No robust live Polymarket data integration yet
- Backtesting based on bookmaker-derived / synthetic data

## Tech Stack
- Python
