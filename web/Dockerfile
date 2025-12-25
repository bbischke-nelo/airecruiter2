FROM node:20-alpine AS builder

WORKDIR /app

# Build arguments for Next.js environment variables
ARG NEXT_PUBLIC_SSO_ENABLED=true
ARG NEXT_PUBLIC_SSO_URL=https://sso.ccfs.com
ARG NEXT_PUBLIC_SSO_CLIENT_ID=recruiter2
ARG NEXT_PUBLIC_DEV_LOGIN_ENABLED=false
ARG NEXT_PUBLIC_API_URL=/recruiter2/api
ARG NEXT_PUBLIC_APP_URL=https://admin.ccfs.com/recruiter2

# Set environment variables for build
ENV NEXT_PUBLIC_SSO_ENABLED=$NEXT_PUBLIC_SSO_ENABLED
ENV NEXT_PUBLIC_SSO_URL=$NEXT_PUBLIC_SSO_URL
ENV NEXT_PUBLIC_SSO_CLIENT_ID=$NEXT_PUBLIC_SSO_CLIENT_ID
ENV NEXT_PUBLIC_DEV_LOGIN_ENABLED=$NEXT_PUBLIC_DEV_LOGIN_ENABLED
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL

# Copy package files
COPY web/package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy application code
COPY web/ .

# Build the application
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 -G nodejs

# Copy standalone build
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/recruiter2/health || exit 1

# Start the standalone server
CMD ["node", "server.js"]
