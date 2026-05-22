FROM node:20-alpine

WORKDIR /app

COPY frontend/ReactApp/package*.json ./
RUN npm ci --legacy-peer-deps

COPY frontend/ReactApp .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
