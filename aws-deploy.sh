#!/bin/bash

# AWS Deployment Script for Matrimonial Webhook Server
# This script provides step-by-step instructions for deploying to AWS

echo "🚀 AWS Deployment Script for Matrimonial Webhook Server"
echo "======================================================"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first:"
    echo "   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install it first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Prerequisites check passed!"
echo ""

echo "📋 Deployment Options:"
echo "1. AWS EC2 (Traditional server)"
echo "2. AWS ECS (Container service)"
echo "3. AWS Lambda (Serverless)"
echo "4. AWS App Runner (Managed container service)"
echo ""

read -p "Choose deployment option (1-4): " choice

case $choice in
    1)
        echo "🔧 Deploying to AWS EC2..."
        deploy_ec2
        ;;
    2)
        echo "🔧 Deploying to AWS ECS..."
        deploy_ecs
        ;;
    3)
        echo "🔧 Deploying to AWS Lambda..."
        deploy_lambda
        ;;
    4)
        echo "🔧 Deploying to AWS App Runner..."
        deploy_app_runner
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

deploy_ec2() {
    echo ""
    echo "📝 EC2 Deployment Steps:"
    echo "========================"
    echo ""
    echo "1. Create EC2 Instance:"
    echo "   - Go to AWS Console → EC2 → Launch Instance"
    echo "   - Choose Amazon Linux 2023 AMI"
    echo "   - Instance type: t3.micro (free tier) or t3.small"
    echo "   - Configure Security Group:"
    echo "     * HTTP (80) - Allow from anywhere"
    echo "     * HTTPS (443) - Allow from anywhere"
    echo "     * Custom TCP (5000) - Allow from anywhere"
    echo "     * SSH (22) - Allow from your IP"
    echo ""
    echo "2. Connect to your EC2 instance:"
    echo "   ssh -i your-key.pem ec2-user@your-instance-ip"
    echo ""
    echo "3. Install Docker on EC2:"
    echo "   sudo yum update -y"
    echo "   sudo yum install -y docker"
    echo "   sudo systemctl start docker"
    echo "   sudo systemctl enable docker"
    echo "   sudo usermod -a -G docker ec2-user"
    echo "   # Logout and login again"
    echo ""
    echo "4. Clone your repository:"
    echo "   git clone <your-repo-url>"
    echo "   cd <your-project-directory>"
    echo ""
    echo "5. Set environment variables:"
    echo "   export WEBHOOK_SECRET='your-secret-here'"
    echo "   export SENDER_EMAIL='your-email@gmail.com'"
    echo "   export SENDER_PASSWORD='your-app-password'"
    echo "   export ADMIN_EMAIL='admin@example.com'"
    echo ""
    echo "6. Build and run Docker container:"
    echo "   docker build -t webhook-server ."
    echo "   docker run -d -p 5000:5000 --env-file .env webhook-server"
    echo ""
    echo "7. Set up Nginx (optional, for HTTPS):"
    echo "   sudo yum install -y nginx"
    echo "   # Configure nginx to proxy to port 5000"
    echo ""
    echo "✅ Your webhook server will be available at:"
    echo "   http://your-ec2-public-ip:5000"
    echo ""
}

deploy_ecs() {
    echo ""
    echo "📝 ECS Deployment Steps:"
    echo "========================"
    echo ""
    echo "1. Create ECR Repository:"
    echo "   aws ecr create-repository --repository-name matrimonial-webhook"
    echo ""
    echo "2. Build and push Docker image:"
    echo "   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com"
    echo "   docker build -t matrimonial-webhook ."
    echo "   docker tag matrimonial-webhook:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/matrimonial-webhook:latest"
    echo "   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/matrimonial-webhook:latest"
    echo ""
    echo "3. Create ECS Cluster:"
    echo "   aws ecs create-cluster --cluster-name matrimonial-cluster"
    echo ""
    echo "4. Create Task Definition (create task-definition.json first):"
    echo "   aws ecs register-task-definition --cli-input-json file://task-definition.json"
    echo ""
    echo "5. Create Service:"
    echo "   aws ecs create-service --cluster matrimonial-cluster --service-name webhook-service --task-definition matrimonial-webhook:1 --desired-count 1"
    echo ""
}

deploy_lambda() {
    echo ""
    echo "📝 Lambda Deployment Steps:"
    echo "==========================="
    echo ""
    echo "1. Create deployment package:"
    echo "   pip install -r requirements.txt -t ./package"
    echo "   pip install -r webhook_requirements.txt -t ./package"
    echo "   cp *.py ./package/"
    echo "   cp *.json ./package/"
    echo "   cd package && zip -r ../lambda-deployment.zip ."
    echo ""
    echo "2. Create Lambda function:"
    echo "   aws lambda create-function --function-name matrimonial-webhook --runtime python3.12 --handler webhook_server.lambda_handler --zip-file fileb://lambda-deployment.zip"
    echo ""
    echo "3. Set environment variables:"
    echo "   aws lambda update-function-configuration --function-name matrimonial-webhook --environment Variables='{WEBHOOK_SECRET=your-secret,SENDER_EMAIL=your-email,SENDER_PASSWORD=your-password,ADMIN_EMAIL=admin@example.com}'"
    echo ""
}

deploy_app_runner() {
    echo ""
    echo "📝 App Runner Deployment Steps:"
    echo "==============================="
    echo ""
    echo "1. Push your code to GitHub/GitLab"
    echo ""
    echo "2. Go to AWS Console → App Runner → Create service"
    echo ""
    echo "3. Configure:"
    echo "   - Source: GitHub"
    echo "   - Repository: your-repo"
    echo "   - Branch: main"
    echo "   - Build command: pip install -r requirements.txt && pip install -r webhook_requirements.txt"
    echo "   - Start command: python webhook_server.py"
    echo ""
    echo "4. Set environment variables in App Runner console"
    echo ""
    echo "5. Deploy!"
    echo ""
}

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo "1. Choose your preferred deployment method above"
echo "2. Follow the detailed steps provided"
echo "3. Update your Google Apps Script with the new webhook URL"
echo "4. Test the integration"
echo ""
echo "📞 Need help? Check AWS documentation or contact support." 