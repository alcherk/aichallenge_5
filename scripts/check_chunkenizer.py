#!/usr/bin/env python3
"""Check if Chunkenizer is running and optionally provide instructions to start it."""
import argparse
import sys
import subprocess
from pathlib import Path
import httpx


def check_chunkenizer(url: str = "http://localhost:8000") -> bool:
    """Check if Chunkenizer is running."""
    try:
        response = httpx.get(f"{url}/api/health", timeout=5.0)
        if response.status_code == 200:
            print(f"✓ Chunkenizer is running at {url}")
            try:
                data = response.json()
                print(f"  Response: {data}")
            except Exception:
                print(f"  Status: {response.status_code}")
            return True
    except Exception as e:
        print(f"✗ Chunkenizer is not running at {url}")
        print(f"  Error: {e}")
        return False
    return False


def main():
    parser = argparse.ArgumentParser(description="Check if Chunkenizer is running")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Chunkenizer API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--chunkenizer-dir",
        default="../Chunkenizer",
        help="Path to Chunkenizer directory (default: ../Chunkenizer)",
    )
    args = parser.parse_args()
    
    if check_chunkenizer(args.url):
        sys.exit(0)
    
    # Chunkenizer is not running
    chunkenizer_path = Path(args.chunkenizer_dir)
    docker_compose = chunkenizer_path / "docker-compose.yml"
    
    if docker_compose.exists():
        print(f"\nTo start Chunkenizer, run:")
        print(f"  cd {chunkenizer_path}")
        print(f"  docker-compose up -d")
        print(f"\nOr check if Docker is running:")
        print(f"  docker ps")
    else:
        print(f"\nChunkenizer directory not found at {chunkenizer_path}")
        print(f"Please start Chunkenizer manually or update --url")
    
    sys.exit(1)


if __name__ == "__main__":
    main()
