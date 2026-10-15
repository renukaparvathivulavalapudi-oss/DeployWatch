
pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                bat '"C:\\Users\\IIIT\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" --version'
                bat '"C:\\Users\\IIIT\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m venv venv'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat 'venv\\Scripts\\python -m pip install --upgrade pip'
                bat 'venv\\Scripts\\python -m pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                bat 'venv\\Scripts\\python -m pytest -v'
            }
        }
    }

    post {
        success {
            echo 'DeployWatch CI pipeline completed successfully!'
        }
        failure {
            echo 'DeployWatch CI pipeline failed. Check the console output.'
        }
    }
}
