FROM --platform=linux/x86_64 sweb.env.py.x86_64.703b2ae04f531f7e0b17eb:latest

COPY ./setup_repo.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_repo.sh
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
