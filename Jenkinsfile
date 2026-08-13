pipeline {
    agent none

    options {
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 120, unit: 'MINUTES')
        buildDiscarder(
            logRotator(
                numToKeepStr: '30',
                artifactNumToKeepStr: '15'
            )
        )
        skipDefaultCheckout(true)
    }

    environment {
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        HF_HUB_OFFLINE = '1'
        TRANSFORMERS_OFFLINE = '1'
        AI_ENABLE_GRPC = 'false'
        AI_ENV_FILE = '/dev/null'
    }

    stages {
        stage('CI and security gates') {
            agent {
                label 'docker-linux'
            }

            stages {
                stage('Checkout') {
                    steps {
                        checkout scm

                        script {
                            env.GIT_SHA = sh(
                                script: 'git rev-parse HEAD',
                                returnStdout: true
                            ).trim()

                            if (!(env.GIT_SHA ==~ /[0-9a-f]{40}/)) {
                                error(
                                    'Unable to resolve a full immutable Git SHA'
                                )
                            }

                            env.IMAGE_TAG =
                                "solar-ai-ci:${env.GIT_SHA}"
                        }

                        sh 'git diff --check'
                    }
                }

                stage('Python CI') {
                    steps {
                        sh '''
                            set -eu

                            python3.11 -m venv .venv-ci

                            .venv-ci/bin/python -m pip install --upgrade \
                              pip==25.3 \
                              setuptools==84.0.0 \
                              wheel==0.46.3

                            .venv-ci/bin/python -m pip install \
                              --index-url https://download.pytorch.org/whl/cpu \
                              torch==2.6.0

                            .venv-ci/bin/python -m pip install \
                              --require-hashes \
                              -r requirements-runtime.lock

                            .venv-ci/bin/python -m pip install \
                              -r requirements-dev.txt

                            .venv-ci/bin/python -m pip check

                            .venv-ci/bin/ruff check \
                              main.py \
                              src \
                              scripts \
                              tests \
                              deploy/scripts

                            .venv-ci/bin/pytest tests \
                              --junitxml=test-results/pytest.xml \
                              --cov=src \
                              --cov-report=term-missing \
                              --cov-report=xml:coverage.xml \
                              --cov-fail-under=85

                            .venv-ci/bin/python \
                              deploy/scripts/verify-models.py
                        '''
                    }

                    post {
                        always {
                            junit(
                                allowEmptyResults: true,
                                testResults: 'test-results/*.xml'
                            )

                            archiveArtifacts(
                                allowEmptyArchive: true,
                                artifacts: 'coverage.xml'
                            )
                        }
                    }
                }

                stage('Contracts and deployment config') {
                    steps {
                        sh '''
                            set -eu

                            .venv-ci/bin/python scripts/gen_proto.py

                            git diff --exit-code -- \
                              protos \
                              src/grpc_gen

                            shellcheck deploy/scripts/*.sh

                            ci_secret_file="$(mktemp)"

                            cleanup_contract_validation() {
                              rm -f "${ci_secret_file}"
                            }

                            trap cleanup_contract_validation EXIT

                            AI_IMAGE="${IMAGE_TAG}" \
                            AI_SECRETS_FILE="${ci_secret_file}" \
                              docker compose \
                                --env-file deploy/host.env.example \
                                -f docker-compose.prod.yml \
                                config --quiet

                            docker run --rm \
                              --entrypoint caddy \
                              -e AI_PUBLIC_DOMAIN=ai.solars.io.vn \
                              -e ACME_EMAIL=ops@solars.io.vn \
                              -v "${WORKSPACE}/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
                              caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d \
                              validate \
                              --config /etc/caddy/Caddyfile \
                              --adapter caddyfile
                        '''
                    }
                }

                stage('Filesystem security scan') {
                    steps {
                        sh '''
                            set -eu

                            trivy fs \
                              --exit-code 1 \
                              --severity HIGH,CRITICAL \
                              --scanners vuln,secret,misconfig \
                              --format json \
                              --output trivy-fs.json \
                              .
                        '''
                    }

                    post {
                        always {
                            archiveArtifacts(
                                allowEmptyArchive: true,
                                artifacts: 'trivy-fs.json'
                            )
                        }
                    }
                }

                stage('Build immutable image') {
                    steps {
                        sh '''
                            set -eu

                            docker build \
                              --pull \
                              --build-arg BUILD_COMMIT="${GIT_SHA}" \
                              --build-arg BUILD_VERSION="${GIT_SHA}" \
                              --tag "${IMAGE_TAG}" \
                              .
                        '''
                    }
                }

                stage('Container verification') {
                    steps {
                        sh '''
                            set -eu

                            container="solar-ai-ci-${BUILD_NUMBER}"

                            cleanup_container() {
                              docker rm -f "${container}" \
                                >/dev/null 2>&1 || true
                            }

                            trap cleanup_container EXIT

                            docker run -d \
                              --name "${container}" \
                              --read-only \
                              --tmpfs /tmp:rw,noexec,nosuid,size=512m,uid=10001,gid=10001,mode=1777 \
                              --tmpfs /data:rw,noexec,nosuid,size=256m,uid=10001,gid=10001,mode=0750 \
                              -e AI_ENABLE_GRPC=true \
                              -e AI_REQUIRE_LFP=true \
                              -e AI_PRELOAD_RAG=true \
                              -e AI_REQUIRE_RAG=true \
                              -e AI_TORCH_COMPILE=false \
                              -e AI_DATA_DIR=/data \
                              -e AI_KB_ROOT=/data/kb \
                              -e AI_KB_DIR=/data/kb/current \
                              -e AI_PRESCRIPTION_HISTORY_DIR=/data/prescription-history \
                              -e AI_CLASSIFICATION_FEEDBACK_DIR=/data/classification-feedback \
                              "${IMAGE_TAG}"

                            attempts=0

                            until docker exec \
                              "${container}" \
                              python \
                              /app/deploy/scripts/smoke-test.py
                            do
                              attempts=$((attempts + 1))

                              if [ "$(docker inspect --format '{{.State.Running}}' "${container}")" != "true" ]; then
                                docker logs "${container}"
                                exit 1
                              fi

                              if [ "${attempts}" -ge 24 ]; then
                                docker logs "${container}"
                                exit 1
                              fi

                              sleep 5
                            done
                        '''
                    }
                }

                stage('Image security and SBOM') {
                    steps {
                        sh '''
                            set -eu

                            if ! trivy image \
                              --ignore-unfixed \
                              --exit-code 1 \
                              --severity HIGH,CRITICAL \
                              --format json \
                              --output trivy-image.json \
                              "${IMAGE_TAG}"
                            then
                              trivy convert \
                                --format table \
                                --severity HIGH,CRITICAL \
                                trivy-image.json

                              exit 1
                            fi

                            SYFT_FILE_METADATA_SELECTION=none \
                              syft "${IMAGE_TAG}" \
                                --override-default-catalogers \
                                  dpkg-db-cataloger,python-installed-package-cataloger,safetensors-cataloger \
                                --select-catalogers=-file \
                                --parallelism 2 \
                                -o cyclonedx-json=sbom.cdx.json
                        '''
                    }

                    post {
                        always {
                            archiveArtifacts(
                                allowEmptyArchive: true,
                                artifacts:
                                    'trivy-image.json,sbom.cdx.json'
                            )
                        }
                    }
                }
            }

            post {
                always {
                    sh '''
                        if [ -n "${IMAGE_TAG:-}" ]; then
                          docker image rm "${IMAGE_TAG}" \
                            >/dev/null 2>&1 || true
                        fi
                    '''

                    deleteDir()
                }
            }
        }

        /*
         * Stage này không giữ executor docker-linux.
         *
         * Sau khi CI and security gates kết thúc, executor được giải phóng.
         * solar-ai-production có thể nhận chính executor đó và bắt đầu deploy.
         */
        stage('Request trusted production release') {
            when {
                allOf {
                    branch 'main'

                    expression {
                        env.CHANGE_ID == null
                    }
                }
            }

            steps {
                build(
                    job: 'solar-ai-production',
                    wait: true,
                    propagate: true,
                    parameters: [
                        string(
                            name: 'GIT_SHA',
                            value: env.GIT_SHA
                        )
                    ]
                )
            }
        }
    }

    post {
        success {
            echo "AI pipeline succeeded for ${env.GIT_SHA}"
        }

        failure {
            echo(
                'AI pipeline failed; production was not changed ' +
                'or was rolled back'
            )
        }

        aborted {
            echo(
                'AI pipeline was aborted; verify the production ' +
                'job before retrying'
            )
        }
    }
}
