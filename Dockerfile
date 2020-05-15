FROM lambgeo/lambda:gdal2.4-py3.7-geolayer

WORKDIR /tmp

ENV PYTHONUSERBASE=/var/task

COPY cogeo_tiler/ cogeo_tiler/
COPY setup.py setup.py

# Install dependencies
RUN pip install . --user
RUN rm -rf cogeo_tiler setup.py