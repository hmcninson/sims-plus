"""
Script to bulk assign subjects to all classes for a tenant.

Usage:
    python assign_subjects_to_classes.py <subdomain> <email> <password>

Example:
    python assign_subjects_to_classes.py brightfutureacademy admin@school.edu MyPassword123
"""
import asyncio
import sys
import httpx

BASE_URL = "http://localhost:8000/api/v1"

# Get from command line args or use defaults
if len(sys.argv) >= 4:
    SUBDOMAIN = sys.argv[1]
    EMAIL = sys.argv[2]
    PASSWORD = sys.argv[3]
else:
    print("Usage: python assign_subjects_to_classes.py <subdomain> <email> <password>")
    print("Example: python assign_subjects_to_classes.py brightfutureacademy admin@school.edu MyPassword123")
    sys.exit(1)


async def main():
    async with httpx.AsyncClient() as client:
        headers = {"X-Subdomain": SUBDOMAIN}

        # 1. Login
        print("Logging in...")
        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            headers=headers,
            json={"email": EMAIL, "password": PASSWORD},
        )

        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return

        token = login_response.json()["access_token"]
        headers["Authorization"] = f"Bearer {token}"
        print("  Logged in successfully")

        # 2. Get all classes
        print("\nFetching classes...")
        classes_response = await client.get(
            f"{BASE_URL}/academic/classes",
            headers=headers,
        )

        if classes_response.status_code != 200:
            print(f"Failed to get classes: {classes_response.text}")
            return

        classes = classes_response.json()
        print(f"  Found {len(classes)} classes")

        # 3. Get all subjects
        print("\nFetching subjects...")
        subjects_response = await client.get(
            f"{BASE_URL}/academic/subjects",
            headers=headers,
        )

        if subjects_response.status_code != 200:
            print(f"Failed to get subjects: {subjects_response.text}")
            return

        subjects = subjects_response.json()
        print(f"  Found {len(subjects)} subjects")

        # 4. For each class, check existing assignments and add missing ones
        print("\n" + "=" * 60)
        print("ASSIGNING SUBJECTS TO CLASSES")
        print("=" * 60)

        for cls in classes:
            class_id = cls["id"]
            class_name = cls["name"]
            level_category = cls.get("level_category", "")

            print(f"\n{class_name} (Category: {level_category})")

            # Get existing class subjects
            existing_response = await client.get(
                f"{BASE_URL}/academic/classes/{class_id}/subjects",
                headers=headers,
            )

            existing_subject_ids = set()
            if existing_response.status_code == 200:
                existing = existing_response.json()
                existing_subject_ids = {cs["subject_id"] for cs in existing}
                print(f"  Already has {len(existing_subject_ids)} subjects assigned")

            # Determine which subjects to assign based on level category
            subjects_to_assign = []

            for subject in subjects:
                subject_id = subject["id"]
                subject_name = subject["name"]
                subject_category = subject.get("category", "")

                # Skip if already assigned
                if subject_id in existing_subject_ids:
                    continue

                # Filter logic based on class level
                # Preschool: Focus on foundational subjects
                # Primary/JHS/SHS: All academic subjects

                if level_category == "preschool":
                    # Preschool typically has simplified subjects
                    preschool_subjects = [
                        "english", "mathematics", "math", "numeracy",
                        "reading", "writing", "phonics", "creative arts",
                        "physical education", "pe", "science", "social studies"
                    ]
                    if any(ps in subject_name.lower() for ps in preschool_subjects):
                        subjects_to_assign.append(subject)
                else:
                    # For other levels, assign all subjects
                    subjects_to_assign.append(subject)

            # Assign subjects
            assigned_count = 0
            for subject in subjects_to_assign:
                assign_response = await client.post(
                    f"{BASE_URL}/academic/classes/{class_id}/subjects",
                    headers=headers,
                    json={
                        "subject_id": subject["id"],
                        "is_compulsory": True,
                        "periods_per_week": 5,
                    },
                )

                if assign_response.status_code in [200, 201]:
                    assigned_count += 1
                else:
                    print(f"    Failed to assign {subject['name']}: {assign_response.status_code}")

            if assigned_count > 0:
                print(f"  ✓ Assigned {assigned_count} new subjects")
            else:
                print(f"  - No new subjects to assign")

        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
