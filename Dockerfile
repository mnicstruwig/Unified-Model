FROM python:3.8

# set the working dir in the container
WORKDIR /src

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY data data

COPY flux_modeller flux_modeller
RUN cd flux_modeller && pip install .

COPY unified_model unified_model
COPY setup.py .
RUN pip install .

COPY script.py .

CMD ["python", "./script.py"]