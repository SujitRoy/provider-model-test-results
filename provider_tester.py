import asyncio
import aiohttp
import json
import time
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TestResult:
    provider: str
    model: str
    working: bool
    response_time: float
    error: str = None
    media_type: str = None

class CustomAPITester:
    def __init__(self, custom_api_url: str):
        self.custom_api_url = custom_api_url.rstrip('/')
        self.working_dir = "working"
        os.makedirs(self.working_dir, exist_ok=True)
        
        self.test_messages = [
            {"role": "user", "content": "You must respond with exactly one word: 'Yes'"}
        ]
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.semaphore = asyncio.Semaphore(5)

    async def fetch_providers(self, session: aiohttp.ClientSession) -> List[str]:
        try:
            async with session.get(
                f"{self.custom_api_url}/v1/providers",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    providers = await response.json()
                    provider_ids = [p.get('id') for p in providers if p.get('id') and p.get('id') != "Custom"]
                    self.logger.info(f"Found {len(provider_ids)} providers")
                    return provider_ids
                else:
                    self.logger.error(f"Failed to fetch providers: {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"Error fetching providers: {e}")
            return []

    async def fetch_provider_models(self, session: aiohttp.ClientSession, provider_id: str) -> Tuple[str, List[Dict]]:
        try:
            url = f"{self.custom_api_url}/api/{provider_id}/models"
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('data', [])
                    self.logger.info(f"{provider_id}: {len(models)} models")
                    for model in models:
                        print(f"  Found model: {provider_id} | {model.get('id')}")
                    return provider_id, models
                else:
                    self.logger.warning(f"{provider_id}: Failed to fetch models - {response.status}")
                    return provider_id, []
        except Exception as e:
            self.logger.warning(f"{provider_id}: Error - {e}")
            return provider_id, []

    def determine_media_type(self, model: Dict) -> str:
        model_type = model.get('type', '')
        if model_type == 'chat':
            return 'text'
        
        if model.get('video', False):
            return 'video'
        if model.get('audio', False):
            return 'audio'
        if model.get('image', False):
            return 'image'
        if model.get('vision', False):
            return 'vision'
        
        return 'text'

    def validate_response_content(self, content: str) -> Tuple[bool, str]:
        if not content or not content.strip():
            return False, "Empty response"
        
        content_lower = content.lower().strip()
        
        if content_lower == 'yes':
            return True, None
        
        if 'yes' in content_lower:
            return True, None
        
        return False, "Response did not contain 'Yes'"

    async def test_model(self, session: aiohttp.ClientSession, provider_id: str, model: Dict) -> TestResult:
        model_id = model.get('id')
        media_type = self.determine_media_type(model)
        
        print(f"\nTesting: {provider_id} | {model_id}")
        
        async with self.semaphore:
            start_time = time.time()
            try:
                endpoint = f"{self.custom_api_url}/api/{provider_id}/chat/completions"
                payload = {
                    "model": model_id,
                    "messages": self.test_messages,
                    "stream": False,
                    "max_tokens": 10
                }
                
                async with session.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        try:
                            response_data = await response.json()
                            
                            if 'choices' not in response_data or len(response_data['choices']) == 0:
                                print(f"  FAILED: {provider_id}|{model_id} - No choices in response")
                                return TestResult(
                                    provider_id, model_id, False, response_time, 
                                    "No choices in response", media_type
                                )
                            
                            choice = response_data['choices'][0]
                            if 'message' not in choice or 'content' not in choice['message']:
                                print(f"  FAILED: {provider_id}|{model_id} - Missing content")
                                return TestResult(
                                    provider_id, model_id, False, response_time,
                                    "Missing content", media_type
                                )
                            
                            content = choice['message']['content']
                            print(f"  Response: {content[:100]}{'...' if len(content) > 100 else ''}")
                            
                            is_valid, error_msg = self.validate_response_content(content)
                            
                            if is_valid:
                                print(f"  WORKING: {provider_id}|{model_id}|{media_type}")
                                return TestResult(
                                    provider_id, model_id, True, response_time, 
                                    media_type=media_type
                                )
                            else:
                                print(f"  FAILED: {provider_id}|{model_id} - {error_msg}")
                                return TestResult(
                                    provider_id, model_id, False, response_time,
                                    error_msg, media_type
                                )
                                
                        except json.JSONDecodeError:
                            print(f"  FAILED: {provider_id}|{model_id} - Invalid JSON")
                            return TestResult(
                                provider_id, model_id, False, response_time,
                                "Invalid JSON", media_type
                            )
                    else:
                        print(f"  FAILED: {provider_id}|{model_id} - HTTP {response.status}")
                        return TestResult(
                            provider_id, model_id, False, response_time,
                            f"HTTP {response.status}", media_type
                        )
                        
            except asyncio.TimeoutError:
                print(f"  FAILED: {provider_id}|{model_id} - Timeout")
                return TestResult(
                    provider_id, model_id, False, time.time() - start_time,
                    "Timeout", media_type
                )
            except Exception as e:
                print(f"  FAILED: {provider_id}|{model_id} - {str(e)[:100]}")
                return TestResult(
                    provider_id, model_id, False, time.time() - start_time,
                    str(e)[:100], media_type
                )

    async def test_all_models(self) -> List[TestResult]:
        self.logger.info("="*60)
        self.logger.info("TESTING CUSTOM API")
        self.logger.info("="*60)
        
        async with aiohttp.ClientSession() as session:
            provider_ids = await self.fetch_providers(session)
            if not provider_ids:
                self.logger.error("No providers found")
                return []
            
            self.logger.info(f"Fetching models from {len(provider_ids)} providers in parallel")
            
            tasks = [self.fetch_provider_models(session, pid) for pid in provider_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_models = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to fetch models for {provider_ids[i]}: {result}")
                    continue
                provider_id, models = result
                for model in models:
                    all_models.append((provider_id, model))
            
            self.logger.info(f"Total models to test: {len(all_models)}")
            
            if not all_models:
                self.logger.error("No models found")
                return []
            
            self.logger.info("="*60)
            self.logger.info(f"TESTING {len(all_models)} MODELS (max 5 concurrent)")
            self.logger.info("="*60)
            print("\n" + "-"*60)
            print("TEST PROGRESS")
            print("-"*60)
            
            test_tasks = [self.test_model(session, provider_id, model) for provider_id, model in all_models]
            results = await asyncio.gather(*test_tasks, return_exceptions=True)
            
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    provider_id, model = all_models[i]
                    model_id = model.get('id')
                    self.logger.error(f"Unhandled exception for {provider_id}|{model_id}: {result}")
                    final_results.append(TestResult(
                        provider_id, model_id, False, 0.0, 
                        f"Exception: {str(result)[:50]}", 
                        self.determine_media_type(model)
                    ))
                else:
                    final_results.append(result)
            
            print("\n" + "-"*60)
            print("TEST SUMMARY")
            print("-"*60)
            for result in final_results:
                if result.working:
                    print(f"WORKING: {result.provider}|{result.model}|{result.media_type}")
                else:
                    print(f"FAILED: {result.provider}|{result.model} - {result.error}")
            
            return final_results

    def save_working_results(self, results: List[TestResult]):
        working_results = [r for r in results if r.working]
        working_results.sort(key=lambda x: (x.provider, x.model))
        
        filepath = os.path.join(self.working_dir, "working_results.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            for result in working_results:
                f.write(f"{result.provider}|{result.model}|{result.media_type or 'text'}\n")
        
        self.logger.info("="*60)
        self.logger.info("RESULTS SAVED")
        self.logger.info("="*60)
        self.logger.info(f"File: {filepath}")
        self.logger.info(f"Working models: {len(working_results)}")
        
        return filepath

    def print_summary(self, results: List[TestResult]):
        working_results = [r for r in results if r.working]
        
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"Total Models Tested: {len(results)}")
        print(f"Working Models: {len(working_results)}")
        print(f"Failed Models: {len(results) - len(working_results)}")
        
        if results:
            print(f"Success Rate: {(len(working_results)/len(results)*100):.1f}%")
        
        if working_results:
            providers = {}
            for result in working_results:
                providers[result.provider] = providers.get(result.provider, 0) + 1
            
            print("\nWorking Models by Provider:")
            print("-" * 60)
            for provider, count in sorted(providers.items()):
                print(f"   {provider}: {count} models")

async def main():
    API_URL = os.getenv('CUSTOM_API_URL')
    
    if not API_URL:
        print("="*60)
        print("ERROR: CUSTOM_API_URL not set in .env file")
        print("Please create a .env file with:")
        print("CUSTOM_API_URL=http://your-server-ip:1337")
        print("="*60)
        return
    
    print("="*60)
    print("CUSTOM API PROVIDER/MODEL TESTER")
    print("="*60)
    print(f"Testing API at: {API_URL}")
    print(f"Max concurrent tests: 5")
    print(f"Timeout per model: 60 seconds")
    print("="*60)
    
    start_time = time.time()
    tester = CustomAPITester(API_URL)
    
    print("\nStarting tests...")
    results = await tester.test_all_models()
    
    if results:
        tester.save_working_results(results)
        tester.print_summary(results)
        
        elapsed = time.time() - start_time
        print(f"\nTotal execution time: {elapsed:.1f} seconds")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(os.path.join(tester.working_dir, "last_run.txt"), 'w') as f:
            f.write(f"Last run: {timestamp}\n")
            f.write(f"Execution time: {elapsed:.1f}s\n")
            f.write(f"Working models: {len([r for r in results if r.working])}\n")
    else:
        print("\nNo results to save!")
    
    print("\n" + "="*60)
    print("TESTING COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
