import asyncio
import aiohttp
import json
import time
import os
from typing import Dict, List, Tuple, Any
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
            {"role": "user", "content": "Hello! Reply with 'Yes' if you can respond."}
        ]
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    async def fetch_providers(self) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.custom_api_url}/v1/providers",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        providers = await response.json()
                        provider_ids = [p.get('id') for p in providers if p.get('id') and p.get('id') != "Custom"]
                        self.logger.info(f"Found {len(provider_ids)} providers from /v1/providers (excluded 'Custom')")
                        for pid in provider_ids:
                            self.logger.info(f"   - {pid}")
                        return provider_ids
                    else:
                        self.logger.error(f"Failed to fetch providers: {response.status}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching providers: {e}")
            return []

    async def fetch_provider_models(self, session: aiohttp.ClientSession, provider_id: str) -> List[Dict]:
        try:
            url = f"{self.custom_api_url}/api/{provider_id}/models"
            self.logger.info(f"   Fetching models from: {url}")
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('data', [])
                    self.logger.info(f"   {provider_id}: {len(models)} models found")
                    return models
                else:
                    self.logger.warning(f"   {provider_id}: Failed to fetch models - {response.status}")
                    return []
        except Exception as e:
            self.logger.warning(f"   {provider_id}: Error - {e}")
            return []

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

    async def test_model(self, session: aiohttp.ClientSession, provider_id: str, model: Dict) -> TestResult:
        start_time = time.time()
        model_id = model.get('id')
        media_type = self.determine_media_type(model)
        
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
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    response_data = await response.json()
                    working = 'choices' in response_data and len(response_data['choices']) > 0
                    
                    return TestResult(
                        provider=provider_id,
                        model=model_id,
                        working=working,
                        response_time=response_time,
                        media_type=media_type
                    )
                else:
                    return TestResult(
                        provider=provider_id,
                        model=model_id,
                        working=False,
                        response_time=response_time,
                        error=f"HTTP {response.status}",
                        media_type=media_type
                    )
                
        except asyncio.TimeoutError:
            return TestResult(
                provider=provider_id,
                model=model_id,
                working=False,
                response_time=time.time() - start_time,
                error="Timeout",
                media_type=media_type
            )
        except Exception as e:
            return TestResult(
                provider=provider_id,
                model=model_id,
                working=False,
                response_time=time.time() - start_time,
                error=str(e)[:100],
                media_type=media_type
            )

    async def test_all_models(self) -> List[TestResult]:
        self.logger.info("\n" + "="*60)
        self.logger.info(f"TESTING CUSTOM API: {self.custom_api_url}")
        self.logger.info("="*60)
        
        provider_ids = await self.fetch_providers()
        if not provider_ids:
            self.logger.error("No providers found (or all were excluded)")
            return []
        
        self.logger.info(f"\nProvider IDs from /v1/providers (excluding 'Custom'): {provider_ids}")
        
        all_models = []
        async with aiohttp.ClientSession() as session:
            for provider_id in provider_ids:
                self.logger.info(f"\nProcessing provider: {provider_id}")
                models = await self.fetch_provider_models(session, provider_id)
                
                for model in models:
                    all_models.append((provider_id, model))
                    self.logger.info(f"      Found model: {model.get('id')} (type: {model.get('type', 'unknown')})")
        
        self.logger.info(f"\nTOTAL: {len(all_models)} models to test across {len(provider_ids)} providers")
        
        if not all_models:
            self.logger.error("No models found for any provider!")
            return []
        
        self.logger.info("\n" + "="*60)
        self.logger.info("TESTING MODELS WITH CHAT COMPLETIONS")
        self.logger.info("="*60)
        
        results = []
        async with aiohttp.ClientSession() as session:
            for i, (provider_id, model) in enumerate(all_models, 1):
                self.logger.info(f"\nTest {i}/{len(all_models)}: {provider_id} | {model.get('id')}")
                result = await self.test_model(session, provider_id, model)
                results.append(result)
                
                if result.working:
                    self.logger.info(f"   WORKING: {result.provider}|{result.model}|{result.media_type}")
                else:
                    self.logger.info(f"   FAILED: {result.provider}|{result.model} - {result.error}")
                
                await asyncio.sleep(0.1)
        
        return results

    def save_working_results(self, results: List[TestResult]):
        working_results = [r for r in results if r.working]
        working_results.sort(key=lambda x: (x.provider, x.model))
        
        filepath = os.path.join(self.working_dir, "working_results.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            for result in working_results:
                f.write(f"{result.provider}|{result.model}|{result.media_type or 'text'}\n")
        
        self.logger.info(f"\n" + "="*60)
        self.logger.info("RESULTS SAVED")
        self.logger.info("="*60)
        self.logger.info(f"File: {filepath}")
        self.logger.info(f"Total working models: {len(working_results)}")
        
        if working_results:
            self.logger.info("\nContents of working_results.txt:")
            self.logger.info("-" * 60)
            for result in working_results:
                self.logger.info(f"   {result.provider}|{result.model}|{result.media_type or 'text'}")
        
        return filepath

    def print_summary(self, results: List[TestResult]):
        working_results = [r for r in results if r.working]
        
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"API URL: {self.custom_api_url}")
        print(f"Total Models Tested: {len(results)}")
        print(f"Working Models: {len(working_results)}")
        print(f"Failed Models: {len(results) - len(working_results)}")
        
        if results:
            print(f"Success Rate: {(len(working_results)/len(results)*100):.1f}%")
        
        if working_results:
            providers = {}
            for result in working_results:
                providers[result.provider] = providers.get(result.provider, 0) + 1
            
            print("\nWorking Models by Provider (excluded 'Custom'):")
            print("-" * 60)
            for provider, count in sorted(providers.items()):
                print(f"   • {provider}: {count} models")
            
            media_types = {}
            for result in working_results:
                media_types[result.media_type] = media_types.get(result.media_type, 0) + 1
            
            print("\nMedia Type Breakdown:")
            print("-" * 60)
            for media_type, count in sorted(media_types.items()):
                print(f"   • {media_type}: {count} models")

async def main():
    API_URL = os.getenv('CUSTOM_API_URL', 'http://80.225.251.135:1337')
    
    print("="*60)
    print("CUSTOM API PROVIDER/MODEL TESTER")
    print("="*60)
    print(f"Testing API: {API_URL}")
    print("Workflow:")
    print("   1. GET /v1/providers -> Get provider IDs (excluding 'Custom')")
    print("   2. GET /api/{provider}/models -> Get model IDs")
    print("   3. POST /api/{provider}/chat/completions -> Test each model")
    print("   4. Generate working_results.txt -> Provider|Model|MediaType")
    print("="*60)
    
    tester = CustomAPITester(API_URL)
    
    print("\nStarting tests...")
    results = await tester.test_all_models()
    
    if results:
        tester.save_working_results(results)
        tester.print_summary(results)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(os.path.join(tester.working_dir, "last_run.txt"), 'w') as f:
            f.write(f"Last successful run: {timestamp}\n")
            f.write(f"Working models: {len([r for r in results if r.working])}\n")
    else:
        print("\nNo results to save!")
    
    print("\n" + "="*60)
    print("TESTING COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
