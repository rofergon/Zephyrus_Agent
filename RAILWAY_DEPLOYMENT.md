# Railway Deployment Guide

This document provides instructions for deploying the Zephyrus Agent to Railway using GitHub integration.

## Prerequisites

- A GitHub account with your project repository
- A Railway account (sign up at https://railway.app/)
- Your code pushed to the GitHub repository

## Deployment Steps

### 1. Initial Setup

1. Log in to your Railway account
2. Create a new project by clicking "New Project"
3. Select "Deploy from GitHub repo"
4. Configure the GitHub app and select your repository
5. Railway will automatically detect your Python project

### 2. Environment Variables

After deployment, set up your environment variables in the Railway dashboard:

1. Go to your project in the Railway dashboard
2. Navigate to the "Variables" tab
3. Add the necessary environment variables from your `.env.railway` file
   - Make sure to set `WS_HOST=0.0.0.0` and `WS_PORT=$PORT`
   - Add your `OPENAI_API_KEY` and any other required variables
   - If using a database, configure those variables as well

### 3. Networking

1. Go to the "Settings" tab of your project
2. Under "Networking", click "Generate Domain"
3. Railway will create a public URL for your application

### 4. Monitoring

- Check deployment logs in the "Deployments" tab
- Monitor your application's status in the "Overview" tab
- View real-time logs in the "Logs" tab

### 5. Continuous Deployment

By default, Railway will automatically deploy new changes when you push to your GitHub repository.

## Troubleshooting

- If the deployment fails, check the logs for error messages
- Ensure all required environment variables are properly set
- Verify that the `Procfile` and `railway.json` files are properly configured
- Make sure your application is binding to the correct host (0.0.0.0) and port ($PORT)

## Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Railway Python Deployment Guide](https://docs.railway.app/guides/python) 