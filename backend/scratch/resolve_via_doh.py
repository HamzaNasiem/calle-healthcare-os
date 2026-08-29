import urllib.request
import json

def lookup_doh(name, type_str="AAAA"):
    url = f"https://dns.google/resolve?name={name}&type={type_str}"
    try:
        req = urllib.request.Request(
            url, 
            headers={'Accept': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"DNS-over-HTTPS results for {name} ({type_str}):")
            if "Answer" in data:
                for answer in data["Answer"]:
                    print(f"  Type {answer['type']}: {answer['data']}")
            else:
                print("  No records found in answer.")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    lookup_doh("db.aabbhuzlzjkosqmvhysm.supabase.co", "AAAA")
    lookup_doh("db.aabbhuzlzjkosqmvhysm.supabase.co", "A")
    lookup_doh("aabbhuzlzjkosqmvhysm.supabase.co", "A")
