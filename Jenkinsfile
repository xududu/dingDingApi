pipeline {
  agent {
    node {
      label '192.168.0.170'
    }

  }
  stages {
    stage('pull') {
      agent {
        node {
          label '192.168.0.170'
        }

      }
      steps {
        sh 'docker pull python:3'
      }
    }

  }
}