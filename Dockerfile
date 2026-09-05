FROM nginx:alpin 

EXPOSE 8501

RUN sed -i 's/listen       80;/listen       8501;/' /etc/nginx/conf.d/default.conf

COPY index.html /usr/share/nginx/html/index.html