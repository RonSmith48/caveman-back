@echo off
echo Starting Django development server with environment: development
set ENV=development
pipenv run python manage.py runserver
pause
