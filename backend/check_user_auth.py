import sys
import os
import asyncio

sys.path.insert(0, r"D:\projects\bytelytic-os-single\backend")
os.chdir(r"D:\projects\bytelytic-os-single\backend")

from src.core.database import supabase, supabase_read

async def main():
    email = "hamza.naseem2027@gmail.com"
    password = "BytelyticClinic2026!"
    print(f"Target email: {email}")
    
    # 1. List users
    try:
        users_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.auth.admin.list_users()
        )
        users = users_res
        
        users_list = []
        if isinstance(users, dict):
            users_list = users.get("users", [])
        elif hasattr(users, "users"):
            users_list = users.users
        else:
            users_list = users
            
        print(f"Total Auth Users: {len(users_list)}")
        
        target_user = None
        for u in users_list:
            u_email = u.get("email") if isinstance(u, dict) else getattr(u, "email", None)
            u_id = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
            print(f"  User: ID={u_id}, Email={u_email}")
            if u_email == email:
                target_user = u
                target_user_id = u_id
                
        if target_user:
            print(f"User {email} exists in Auth. Updating password to {password}...")
            update_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.auth.admin.update_user_by_id(
                    target_user_id,
                    {"password": password}
                )
            )
            print("Password reset successful!")
        else:
            print(f"User {email} DOES NOT exist in Auth. Let's create user...")
            create_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True
                })
            )
            created_user = create_res
            target_user_id = created_user.user.id if hasattr(created_user, "user") else created_user.get("user", {}).get("id")
            print(f"User created with ID: {target_user_id}")
            
        # 2. Check clinics
        clinic_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics").select("*").eq("owner_email", email).execute()
        )
        print(f"Clinics matching {email}: {clinic_res.data}")
        
        if not clinic_res.data:
            print("No clinic found. Creating clinic...")
            new_clinic_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("clinics").insert({
                    "name": "Bytelytic Test Clinic",
                    "owner_email": email,
                    "phone_number": "+1234567890",
                    "timezone": "America/New_York",
                    "business_hours": {
                        "mon": "08:00-17:00", "tue": "08:00-17:00", "wed": "08:00-17:00",
                        "thu": "08:00-17:00", "fri": "08:00-17:00", "sat": "closed", "sun": "closed"
                    }
                }).execute()
            )
            print(f"Created clinic: {new_clinic_res.data}")
            clinic_id = new_clinic_res.data[0]["id"]
        else:
            clinic_id = clinic_res.data[0]["id"]
            
        # 3. Check clinic_users mapping
        mapping_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinic_users").select("*").eq("supabase_user_id", target_user_id).execute()
        )
        print(f"Clinic user mapping: {mapping_res.data}")
        if not mapping_res.data:
            print("No clinic user mapping found. Inserting mapping...")
            new_map = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("clinic_users").insert({
                    "clinic_id": clinic_id,
                    "supabase_user_id": target_user_id,
                    "role": "owner"
                }).execute()
            )
            print(f"Created mapping: {new_map.data}")
            
    except Exception as e:
        print("Error during check/reset:", e)

if __name__ == "__main__":
    asyncio.run(main())
