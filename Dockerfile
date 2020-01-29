FROM remotepixel/amazonlinux:gdal3.0-py3.7-cogeo

WORKDIR /tmp

ENV PYTHONUSERBASE=/var/task

COPY cogeo_tiler/ cogeo_tiler/
COPY setup.py setup.py

# Install dependencies
RUN pip install . --user
RUN rm -rf cogeo_tiler setup.py