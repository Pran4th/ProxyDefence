# Stage 1: Build the Vite React application
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency files first to leverage Docker caching
COPY package.json package-lock.json ./

# Install dependencies cleanly
RUN npm ci

# Copy the rest of the frontend code
COPY . .

# Build the production static files
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy the built assets from the previous stage to Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx config for React Router
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 inside the container
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]