FROM nginx:alpine

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制所有前端页面
COPY *.html /usr/share/nginx/html/

EXPOSE 80
