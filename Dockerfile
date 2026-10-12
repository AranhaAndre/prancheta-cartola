# Só para quem hospedar no Northflank (ou em qualquer lugar que rode container).
# Serve a página já pronta de site/ — o build de dados acontece no GitHub Actions, não aqui.
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/
EXPOSE 8080
