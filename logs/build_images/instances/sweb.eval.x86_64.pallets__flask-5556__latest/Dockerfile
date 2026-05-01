FROM --platform=linux/x86_64 sweb.env.py.x86_64.8815f6e16e5b03e627df14:latest

COPY ./setup_repo.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_repo.sh
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
