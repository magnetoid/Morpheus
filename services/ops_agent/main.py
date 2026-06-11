import base64
import os
import time
from typing import Any

import requests
from fastapi import BackgroundTasks, FastAPI
from github import Github

app = FastAPI(title='Morpheus Ops Agent', version='0.1.0')


def _prometheus_base_url() -> str:
    return os.getenv('PROMETHEUS_BASE_URL', 'http://localhost:9090')


def _create_gitops_pr(target: str, recommended_replicas: int):
    # This assumes the GITHUB_TOKEN is available and the repo is magnetoid/morph
    # Real-world usage requires setting GITHUB_TOKEN and GITHUB_REPO env vars
    token = os.getenv('GITHUB_TOKEN')
    repo_name = os.getenv('GITHUB_REPO', 'magnetoid/morph')
    if not token:
        print('GITHUB_TOKEN not set, skipping GitOps PR.')
        return

    g = Github(token)
    repo = g.get_repo(repo_name)

    file_path = f'k8s/deployment-{target.rsplit("-", maxsplit=1)[-1]}.yaml'
    try:
        contents = repo.get_contents(file_path)
        decoded_content = base64.b64decode(contents.content).decode('utf-8')

        # Super naive YAML replace for replica count
        import re

        new_content = re.sub(
            r'replicas:\s*\d+', f'replicas: {recommended_replicas}', decoded_content
        )

        if new_content == decoded_content:
            print('No change needed.')
            return

        branch_name = f'ops-agent/scale-{target}-{int(time.time())}'
        sb = repo.get_branch('main')
        repo.create_git_ref(ref=f'refs/heads/{branch_name}', sha=sb.commit.sha)

        repo.update_file(
            file_path,
            f'chore: scale {target} to {recommended_replicas} replicas',
            new_content,
            contents.sha,
            branch=branch_name,
        )

        pr = repo.create_pull(
            title=f'Autoscale {target} -> {recommended_replicas} replicas',
            body='Automated GitOps PR by Ops Agent based on Prometheus metrics.',
            head=branch_name,
            base='main',
        )
        print(f'Created GitOps PR: {pr.html_url}')
    except Exception as e:
        print(f'Failed to create GitOps PR: {e}')


@app.get('/healthz')
def healthz() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/scale')
def trigger_scale(
    background_tasks: BackgroundTasks, target: str = 'morpheus-web', replicas: int = 5
) -> dict[str, str]:
    """Manually trigger a GitOps PR for scaling."""
    background_tasks.add_task(_create_gitops_pr, target, replicas)
    return {'status': 'accepted', 'message': f'GitOps PR authoring triggered for {target}'}


@app.get('/recommendations')
def recommendations(background_tasks: BackgroundTasks) -> dict[str, Any]:
    base = _prometheus_base_url().rstrip('/')
    query = 'sum(rate(http_server_request_duration_seconds_count[5m]))'
    started = time.monotonic()
    try:
        resp = requests.get(f'{base}/api/v1/query', params={'query': query}, timeout=3)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        data = {'error': str(e)}

    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Fake logic for demonstration: if traffic > threshold, scale up
    recommended_replicas = 5
    target = 'morpheus-web'
    background_tasks.add_task(_create_gitops_pr, target, recommended_replicas)

    return {
        'elapsed_ms': elapsed_ms,
        'mode': 'gitops',
        'actions': [
            {
                'type': 'autoscaling',
                'target': target,
                'recommendation': f'Scale to {recommended_replicas} replicas via PR',
            },
        ],
        'metrics_probe': data,
    }
