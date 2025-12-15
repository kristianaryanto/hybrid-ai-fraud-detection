### STAGE 1: Build ###
# Gunakan Node.js image untuk membangun aplikasi React
FROM node:18-alpine AS build

# Set working directory
WORKDIR /app

# Salin package.json dan package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Salin sisa kode aplikasi
COPY . .

# Bangun aplikasi untuk production
RUN npm run build

### STAGE 2: Serve ###
# Gunakan Nginx image yang ringan untuk menyajikan konten statis
FROM nginx:stable-alpine

# Salin hasil build dari stage sebelumnya ke direktori default Nginx
COPY --from=build /app/build /usr/share/nginx/html

# Ekspos port 80 (default Nginx)
EXPOSE 80

# Saat container dimulai, Nginx akan otomatis menyajikan file.
CMD ["nginx", "-g", "daemon off;"]