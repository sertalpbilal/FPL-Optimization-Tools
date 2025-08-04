FROM python:3.8-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && apt-get install -y coinor-cbc \
  && apt-get install -y coinor-libcbc-dev \
  && apt-get install -y wget \
  && apt-get purge -y --auto-remove \
  && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app_user

WORKDIR /fpl-optimization

COPY . .

RUN python -m pip install -r requirements.txt

RUN chown -R app_user /fpl-optimization
RUN chmod -R 755 /fpl-optimization

WORKDIR /fpl-optimization/run/

USER app_user

ENTRYPOINT [ "python", "solve_regular.py" ]
CMD [ "bash" ]
