from locust import HttpUser, between, task


class LindaLoadTestUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        # Setup: Authenticate or get API keys if needed
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-agent-token',
        }

    @task(3)
    def cached_query(self):
        """Simulate high-volume repeated queries that should hit the semantic cache."""
        payload = {'messages': [{'role': 'user', 'content': 'What is the status of order #12345?'}]}
        with self.client.post(
            '/api/assistant/chat/', json=payload, headers=self.headers, catch_response=True
        ) as response:
            if response.elapsed.total_seconds() > 1.0:
                response.failure(f'Response too slow: {response.elapsed.total_seconds()}s')
            elif response.status_code == 200:
                response.success()

    @task(1)
    def complex_query(self):
        """Simulate a complex query requiring tool execution and fallback routing."""
        payload = {
            'messages': [
                {
                    'role': 'user',
                    'content': 'Draft a personalized email for customer test@example.com based on their last 3 orders.',
                }
            ]
        }
        self.client.post('/api/assistant/chat/', json=payload, headers=self.headers)


# Run with: locust -f locustfile.py --headless -u 1000 -r 100 --run-time 10m
