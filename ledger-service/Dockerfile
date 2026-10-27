FROM gcc:14 AS cpp
WORKDIR /src
COPY cpp/ .
RUN g++ -std=c++17 -O2 -Wall -Wextra -Werror journal.cpp -o /journal
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY --from=cpp /journal /usr/local/bin/journal
ENV DATABASE_URL=postgresql://demo:demo@db:5432/ledger
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
