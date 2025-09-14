FROM nginx:alpine

# 把你的靜態檔案放到 site/dist/
COPY ./index.html /usr/share/nginx/html/

# 改 Nginx 預設 conf，讓它聽 8080
RUN sed -i 's/listen       80;/listen 8080;/' /etc/nginx/conf.d/default.conf

EXPOSE 8080

