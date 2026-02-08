"""
Test script for Opik connection check.
Run: python test_opik_connection.py
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import modules
try:
    from core.services.opik_client import get_opik_client
    from core.config.settings import get_settings
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"   Make sure you run the script from the project root")
    print(f"   Current directory: {os.getcwd()}")
    print(f"   Script file: {__file__}")
    print(f"   Project root: {project_root}")
    print(f"   sys.path: {sys.path[:3]}")
    sys.exit(1)


def test_opik_connection():
    """Test Opik connection"""
    print("🔍 Checking Opik settings...")
    
    settings = get_settings()
    print(f"  API Key: {'✅ Set' if settings.opik_api_key else '❌ Not set'}")
    print(f"  API Base URL: {settings.opik_api_base_url}")
    print(f"  Project Name: {settings.opik_project_name}")
    print(f"  Enabled: {settings.opik_enabled}")
    print(f"  Configured: {settings.is_opik_configured()}")
    
    print("\n🔍 Initializing Opik client...")
    opik = get_opik_client()
    
    if not opik.is_enabled():
        print("❌ Opik client not initialized!")
        print("   Check settings in .env file")
        return False
    
    print("✅ Opik client initialized successfully!")
    
    print("\n🔍 Testing trace creation...")
    try:
        trace = opik.create_trace(
            name="test_trace",
            thread_id="test_thread_123",
            metadata={"test": True}
        )
        
        if trace:
            print("✅ Trace created successfully!")
            
            print("\n🔍 Testing span creation...")
            span = opik.create_span(
                trace=trace,
                name="test_span",
                node_name="test_node",
                metadata={"test": True}
            )
            
            if span:
                print("✅ Span created successfully!")
                
                print("\n🔍 Testing LLM call logging...")
                opik.log_llm_call(
                    span=span,
                    model_name="gpt-4",
                    provider="openai",
                    messages=[{"role": "user", "content": "Test message"}],
                    response="Test response",
                    latency=100.5
                )
                print("✅ LLM call logged successfully!")
                
                print("\n🎉 All tests passed! Opik integration is working.")
                print("\n📊 Check Opik UI: https://www.comet.com/opik")
                print("   Project: base-library")
                return True
            else:
                print("❌ Failed to create span")
                print("   Opik SDK API may differ from expected")
                return False
        else:
            print("❌ Failed to create trace")
            print("   Check API key and Opik API availability")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Possible causes:")
        print("   1. Invalid API key")
        print("   2. Opik SDK API differs from expected")
        print("   3. Network or Opik API availability issues")
        return False


if __name__ == "__main__":
    success = test_opik_connection()
    sys.exit(0 if success else 1)

