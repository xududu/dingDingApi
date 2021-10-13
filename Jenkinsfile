pipeline {
  agent any
  stages {
    stage('pull') {
      agent {
        node {
          label '172.168.0.170'
        }

      }
      steps {
        sh 'docker pull python:3'
      }
    }

  }
}