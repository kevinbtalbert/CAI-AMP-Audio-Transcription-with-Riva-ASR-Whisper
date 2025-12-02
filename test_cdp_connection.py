"""
Test CDP Connection
Quick script to verify CDP endpoint and authentication
"""
import json
import sys
from pathlib import Path
from config import Config

def test_cdp_configuration():
    """Test CDP configuration"""
    print("=" * 60)
    print("CDP Connection Test")
    print("=" * 60)
    
    # Check deployment type
    print(f"\nDeployment Type: {Config.DEPLOYMENT_TYPE}")
    
    if Config.DEPLOYMENT_TYPE.lower() != "cdp":
        print("⚠️  Warning: DEPLOYMENT_TYPE is not set to 'cdp'")
        print("   Set DEPLOYMENT_TYPE=cdp in .env file")
        return False
    
    # Check CDP Base URL
    print(f"\nCDP Base URL: {Config.CDP_BASE_URL}")
    if not Config.CDP_BASE_URL:
        print("✗ CDP_BASE_URL is not configured")
        print("  Add CDP_BASE_URL to .env file")
        return False
    else:
        print("✓ CDP Base URL configured")
    
    # Check token
    print("\nAuthentication:")
    token = Config.get_cdp_token()
    
    if token:
        print(f"✓ JWT token loaded")
        print(f"  Token prefix: {token[:30]}...")
        print(f"  Token length: {len(token)} characters")
    else:
        print("✗ CDP token not found")
        print(f"  Checked JWT path: {Config.CDP_JWT_PATH}")
        print(f"  CDP_TOKEN env var: {'Set' if Config.CDP_TOKEN else 'Not set'}")
        return False
    
    # Construct endpoint URL
    transcription_url = f"{Config.CDP_BASE_URL}/audio/transcriptions"
    print(f"\nTranscription Endpoint:")
    print(f"  {transcription_url}")
    
    print("\n" + "=" * 60)
    print("Configuration Check Complete")
    print("=" * 60)
    
    print("\nNext Steps:")
    print("1. Ensure you have a test audio file (e.g., test.wav)")
    print("2. Run the application: python app.py")
    print("3. Upload the audio file through the web UI")
    print("4. Click 'Analyze Call' to test transcription")
    
    return True

def test_with_audio_file(audio_file: str):
    """Test transcription with actual audio file"""
    import requests
    
    audio_path = Path(audio_file)
    if not audio_path.exists():
        print(f"✗ Audio file not found: {audio_file}")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"Testing with audio file: {audio_file}")
    print(f"{'=' * 60}")
    
    token = Config.get_cdp_token()
    if not token:
        print("✗ Cannot test without token")
        return False
    
    url = f"{Config.CDP_BASE_URL}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        with open(audio_path, 'rb') as f:
            files = {"file": f}
            data = {"language": Config.DEFAULT_LANGUAGE}
            
            print(f"\nSending request to: {url}")
            print(f"Language: {Config.DEFAULT_LANGUAGE}")
            print(f"File size: {audio_path.stat().st_size} bytes")
            
            response = requests.post(url, headers=headers, files=files, data=data)
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✓ Transcription successful!")
                print("\nResult:")
                print(json.dumps(result, indent=2))
                return True
            else:
                print(f"✗ Error {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"✗ Error during request: {str(e)}")
        return False

if __name__ == "__main__":
    # Test configuration
    config_ok = test_cdp_configuration()
    
    # If audio file provided, test transcription
    if len(sys.argv) > 1 and config_ok:
        audio_file = sys.argv[1]
        test_with_audio_file(audio_file)
    elif config_ok:
        print("\n💡 Tip: Run 'python test_cdp_connection.py <audio_file.wav>' to test transcription")

