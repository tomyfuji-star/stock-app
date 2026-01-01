#!/bin/bash
gunicorn stock_check:app --bind 0.0.0.0:$PORT
