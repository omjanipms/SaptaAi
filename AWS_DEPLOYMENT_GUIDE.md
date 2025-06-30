# 🚀 AWS Deployment Guide for Matrimonial Webhook Server

This guide provides detailed steps to deploy your webhook server to AWS using different methods.

## 📋 Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Docker** installed locally
4. **Git** for version control

## 🎯 Deployment Options

### Option 1: AWS EC2 (Recommended for Beginners)

**Pros:** Simple, full control, cost-effective
**Cons:** Manual management, no auto-scaling

#### Step 1: Create EC2 Instance

1. **Go to AWS Console → EC2 → Launch Instance**
2. **Configure:**
   - **Name:** `matrimonial-webhook-server`
   - **AMI:** Amazon Linux 2023 (free tier eligible)
   - **Instance Type:** `t3.micro` (free tier) or `t3.small`
   - **Key Pair:** Create or select existing key pair
   - **Security Group:** Create new with these rules:
     ```
     HTTP (80) - Allow from anywhere (0.0.0.0/0)
     HTTPS (443) - Allow from anywhere (0.0.0.0/0)
     Custom TCP (5000) - Allow from anywhere (0.0.0.0/0)
     SSH (22) - Allow from your IP only
     ```

#### Step 2: Connect to EC2 Instance

```bash
ssh -i your-key.pem ec2-user@your-instance-public-ip
```

#### Step 3: Install Docker

```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -a -G docker ec2-user

# Logout and login again to apply group changes
exit
# SSH back in
```

#### Step 4: Deploy Application

```bash
# Clone your repository (or upload files)
git clone <your-repo-url>
cd <your-project-directory>

# Create environment file
cat > .env << EOF
WEBHOOK_SECRET=wf_cRjcXgo1RfUuuYtoOyS6RTiiLCs31dZCKLCNTbRk
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
ADMIN_EMAIL=admin@example.com
EOF

# Build and run Docker container
docker build -t webhook-server .
docker run -d -p 5000:5000 --env-file .env --name webhook-container webhook-server

# Check if container is running
docker ps
docker logs webhook-container
```

#### Step 5: Test Deployment

```bash
# Test health endpoint
curl http://localhost:5000/health

# Test from your local machine
curl http://your-ec2-public-ip:5000/health
```

### Option 2: AWS ECS (Container Service)

**Pros:** Managed containers, auto-scaling, high availability
**Cons:** More complex setup

#### Step 1: Create ECR Repository

```bash
aws ecr create-repository --repository-name matrimonial-webhook
```

#### Step 2: Build and Push Docker Image

```bash
# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t matrimonial-webhook .

# Tag image
docker tag matrimonial-webhook:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/matrimonial-webhook:latest

# Push image
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/matrimonial-webhook:latest
```

#### Step 3: Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name matrimonial-cluster
```

#### Step 4: Create Task Definition

1. **Update `task-definition.json`** with your account ID and environment variables
2. **Register task definition:**
   ```bash
   aws ecs register-task-definition --cli-input-json file://task-definition.json
   ```

#### Step 5: Create ECS Service

```bash
aws ecs create-service \
  --cluster matrimonial-cluster \
  --service-name webhook-service \
  --task-definition matrimonial-webhook:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

### Option 3: AWS App Runner (Easiest)

**Pros:** Fully managed, automatic scaling, HTTPS included
**Cons:** Less control, potentially more expensive

#### Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Add AWS deployment files"
git push origin main
```

#### Step 2: Create App Runner Service

1. **Go to AWS Console → App Runner → Create service**
2. **Configure:**
   - **Source:** GitHub
   - **Repository:** Your repository
   - **Branch:** main
   - **Build command:** `pip install -r requirements.txt && pip install -r webhook_requirements.txt`
   - **Start command:** `python webhook_server.py`
   - **Port:** 5000

#### Step 3: Set Environment Variables

In App Runner console, add these environment variables:
- `WEBHOOK_SECRET`: `wf_cRjcXgo1RfUuuYtoOyS6RTiiLCs31dZCKLCNTbRk`
- `SENDER_EMAIL`: `your-email@gmail.com`
- `SENDER_PASSWORD`: `your-app-password`
- `ADMIN_EMAIL`: `admin@example.com`

#### Step 4: Deploy

Click "Create & deploy" and wait for deployment to complete.

## 🔧 Post-Deployment Steps

### 1. Update Google Apps Script

Update your `google_form_webhook.gs` with the new webhook URL:

```javascript
// For EC2
const WEBHOOK_URL = 'http://your-ec2-public-ip:5000/webhook';

// For ECS/App Runner
const WEBHOOK_URL = 'https://your-app-runner-url/webhook';
```

### 2. Test the Integration

1. **Submit a test response to your Google Form**
2. **Check the logs:**
   ```bash
   # For EC2
   docker logs webhook-container
   
   # For ECS
   aws logs describe-log-groups --log-group-name-prefix "/ecs/matrimonial-webhook"
   
   # For App Runner
   # Check App Runner console logs
   ```

### 3. Set up Monitoring

#### CloudWatch Alarms (ECS/App Runner)

```bash
# Create alarm for high CPU usage
aws cloudwatch put-metric-alarm \
  --alarm-name "WebhookServerHighCPU" \
  --alarm-description "High CPU usage on webhook server" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

#### Health Checks

```bash
# Test health endpoint
curl https://your-webhook-url/health

# Expected response:
# {"service":"Matrimonial Webhook Server","status":"healthy","timestamp":"..."}
```

## 🔒 Security Considerations

### 1. Environment Variables

- **Never commit secrets to Git**
- **Use AWS Secrets Manager** for production
- **Rotate secrets regularly**

### 2. Network Security

- **Use VPC** for ECS deployments
- **Restrict security group rules** to minimum required
- **Enable HTTPS** for production

### 3. IAM Roles

- **Use least privilege principle**
- **Create specific roles** for your application
- **Regularly audit permissions**

## 💰 Cost Optimization

### EC2
- **Use Spot Instances** for non-critical workloads
- **Right-size instances** based on usage
- **Use Reserved Instances** for predictable workloads

### ECS
- **Use Fargate Spot** for cost savings
- **Auto-scale based on demand**
- **Monitor resource usage**

### App Runner
- **Use auto-scaling** to scale to zero when not in use
- **Monitor execution time** to optimize costs

## 🚨 Troubleshooting

### Common Issues

1. **Container won't start:**
   ```bash
   docker logs <container-name>
   ```

2. **Permission denied:**
   ```bash
   sudo chown -R ec2-user:ec2-user /path/to/app
   ```

3. **Port already in use:**
   ```bash
   sudo netstat -tulpn | grep :5000
   sudo kill -9 <PID>
   ```

4. **Environment variables not set:**
   ```bash
   docker exec <container-name> env | grep WEBHOOK
   ```

### Logs and Monitoring

```bash
# View application logs
docker logs -f webhook-container

# View system logs
sudo journalctl -u docker

# Monitor resource usage
docker stats
```

## 📞 Support

- **AWS Documentation:** https://docs.aws.amazon.com/
- **AWS Support:** Available with paid plans
- **Community Forums:** AWS Developer Forums

## 🎯 Next Steps

1. **Choose your deployment method**
2. **Follow the detailed steps**
3. **Test the integration**
4. **Set up monitoring and alerts**
5. **Document your deployment process**

---

**Remember:** Always test in a staging environment before deploying to production! 