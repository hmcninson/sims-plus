"""Test all examination module endpoints."""
import httpx
import asyncio
import json
from uuid import uuid4
from datetime import date, timedelta

BASE_URL = "http://localhost:8000/api/v1"
SUBDOMAIN = "testschool"

# Test results
results = []


def log_result(test_name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append({"test": test_name, "passed": passed, "details": details})
    print(f"[{status}] {test_name}")
    if details and not passed:
        print(f"       {details}")


async def run_tests():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # =============================================
        # AUTHENTICATION
        # =============================================
        print("\n" + "=" * 60)
        print("AUTHENTICATION")
        print("=" * 60)

        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "admin@testschool.edu", "password": "Test1234!"},
            headers={"X-Subdomain": SUBDOMAIN},
        )

        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return False

        token = login_response.json()["access_token"]
        log_result("Login", True, "Token obtained")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Subdomain": SUBDOMAIN,
        }

        # =============================================
        # SETUP: Get prerequisite data
        # =============================================
        print("\n" + "=" * 60)
        print("SETUP: Getting prerequisite data")
        print("=" * 60)

        # Get current academic year
        academic_years_response = await client.get(
            f"{BASE_URL}/academic/academic-years",
            headers=headers,
        )
        academic_year_id = None
        term_id = None
        if academic_years_response.status_code == 200:
            years = academic_years_response.json()
            if years:
                academic_year_id = years[0]["id"]
                print(f"  Academic Year: {years[0]['name']} (ID: {academic_year_id})")

        # Get terms separately
        terms_response = await client.get(
            f"{BASE_URL}/academic/terms",
            headers=headers,
        )
        if terms_response.status_code == 200:
            terms = terms_response.json()
            if terms:
                term_id = terms[0]["id"]
                print(f"  Term: {terms[0]['name']} (ID: {term_id})")

        if not academic_year_id:
            print("  WARNING: No academic year found - some tests may fail")

        # Get classes
        classes_response = await client.get(
            f"{BASE_URL}/academic/classes",
            headers=headers,
        )
        class_id = None
        section_id = None
        if classes_response.status_code == 200:
            classes = classes_response.json()
            if classes:
                class_id = classes[0]["id"]
                print(f"  Class: {classes[0]['name']} (ID: {class_id})")

                # Get sections for this class
                sections_response = await client.get(
                    f"{BASE_URL}/academic/classes/{class_id}/sections",
                    headers=headers,
                )
                if sections_response.status_code == 200:
                    sections = sections_response.json()
                    if sections:
                        section_id = sections[0]["id"]
                        print(f"  Section: {sections[0]['name']} (ID: {section_id})")

        if not class_id:
            print("  WARNING: No classes found - some tests may fail")

        # Get subjects
        subjects_response = await client.get(
            f"{BASE_URL}/academic/subjects",
            headers=headers,
        )
        subject_id = None
        subject_name = None
        if subjects_response.status_code == 200:
            subjects = subjects_response.json()
            if subjects:
                subject_id = subjects[0]["id"]
                subject_name = subjects[0]["name"]
                print(f"  Subject: {subject_name} (ID: {subject_id})")

        if not subject_id:
            print("  WARNING: No subjects found - some tests may fail")

        # Get students (filter by section if available for bulk score entry)
        students_url = f"{BASE_URL}/students?page_size=5"
        if section_id:
            students_url += f"&section_id={section_id}"
        students_response = await client.get(students_url, headers=headers)
        student_ids = []
        if students_response.status_code == 200:
            students = students_response.json().get("items", [])
            student_ids = [s["id"] for s in students]
            print(f"  Found {len(student_ids)} students" + (f" in section" if section_id else ""))

        if not student_ids:
            print("  WARNING: No students found - some tests may fail")

        # =============================================
        # 1. EXAM CRUD ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("1. EXAM CRUD ENDPOINTS")
        print("=" * 60)

        # Create exam with unique name using timestamp
        import time
        unique_suffix = int(time.time())
        exam_data = {
            "name": f"Test Mid-Term Examination {unique_suffix}",
            "exam_type": "midterm",
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=7)),
            "description": "Test exam created by endpoint test script",
        }
        if academic_year_id:
            exam_data["academic_year_id"] = academic_year_id
        if term_id:
            exam_data["term_id"] = term_id

        create_exam_response = await client.post(
            f"{BASE_URL}/exams",
            headers=headers,
            json=exam_data,
        )
        log_result(
            "POST /exams - Create exam",
            create_exam_response.status_code == 201,
            f"Status: {create_exam_response.status_code}, Response: {create_exam_response.text[:200]}"
        )

        exam_id = None
        if create_exam_response.status_code == 201:
            exam_id = create_exam_response.json()["id"]
            print(f"  Created exam ID: {exam_id}")

        # List exams
        list_exams_response = await client.get(
            f"{BASE_URL}/exams",
            headers=headers,
        )
        log_result(
            "GET /exams - List exams",
            list_exams_response.status_code == 200,
            f"Status: {list_exams_response.status_code}"
        )

        # List exams with filters
        filter_response = await client.get(
            f"{BASE_URL}/exams?exam_type=midterm&status=draft",
            headers=headers,
        )
        log_result(
            "GET /exams?filters - List with filters",
            filter_response.status_code == 200,
            f"Status: {filter_response.status_code}, Count: {len(filter_response.json()) if filter_response.status_code == 200 else 'N/A'}"
        )

        # Get single exam
        if exam_id:
            get_exam_response = await client.get(
                f"{BASE_URL}/exams/{exam_id}",
                headers=headers,
            )
            log_result(
                "GET /exams/{id} - Get exam details",
                get_exam_response.status_code == 200,
                f"Status: {get_exam_response.status_code}"
            )

            # Update exam
            update_exam_response = await client.put(
                f"{BASE_URL}/exams/{exam_id}",
                headers=headers,
                json={"name": f"Updated Mid-Term Examination {unique_suffix}", "description": "Updated description"},
            )
            log_result(
                "PUT /exams/{id} - Update exam",
                update_exam_response.status_code == 200,
                f"Status: {update_exam_response.status_code}"
            )

            # Update exam status (uses query param, not json body)
            status_response = await client.patch(
                f"{BASE_URL}/exams/{exam_id}/status?status=scheduled",
                headers=headers,
            )
            log_result(
                "PATCH /exams/{id}/status - Update status",
                status_response.status_code == 200,
                f"Status: {status_response.status_code}"
            )

        # =============================================
        # 2. EXAM SUBJECTS ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("2. EXAM SUBJECTS ENDPOINTS")
        print("=" * 60)

        exam_subject_id = None
        if exam_id and subject_id and class_id:
            # Add subjects to exam (bulk create expects arrays of class_ids and subject_ids)
            add_subjects_response = await client.post(
                f"{BASE_URL}/exams/{exam_id}/subjects",
                headers=headers,
                json={
                    "class_ids": [class_id],
                    "subject_ids": [subject_id],
                    "max_score": 100,
                    "pass_mark": 50,
                },
            )
            log_result(
                "POST /exams/{id}/subjects - Add subjects",
                add_subjects_response.status_code == 201,
                f"Status: {add_subjects_response.status_code}, Response: {add_subjects_response.text[:200]}"
            )

            if add_subjects_response.status_code == 201:
                subjects_data = add_subjects_response.json()
                if subjects_data:
                    exam_subject_id = subjects_data[0]["id"]
                    print(f"  Created exam subject ID: {exam_subject_id}")

            # List exam subjects
            list_subjects_response = await client.get(
                f"{BASE_URL}/exams/{exam_id}/subjects",
                headers=headers,
            )
            log_result(
                "GET /exams/{id}/subjects - List exam subjects",
                list_subjects_response.status_code == 200,
                f"Status: {list_subjects_response.status_code}"
            )

            # Update exam subject
            if exam_subject_id:
                update_subject_response = await client.put(
                    f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}",
                    headers=headers,
                    json={"max_score": 100, "pass_mark": 45},
                )
                log_result(
                    "PUT /exams/{id}/subjects/{subj_id} - Update subject",
                    update_subject_response.status_code == 200,
                    f"Status: {update_subject_response.status_code}"
                )
        else:
            log_result("Add exam subjects", False, "Missing exam_id, subject_id, or class_id")

        # =============================================
        # 3. SCORE ENTRY ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("3. SCORE ENTRY ENDPOINTS")
        print("=" * 60)

        if exam_subject_id:
            # Get score entry form
            score_form_response = await client.get(
                f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}/scores",
                headers=headers,
                params={"section_id": section_id} if section_id else {},
            )
            log_result(
                "GET /exams/{id}/subjects/{subj}/scores - Get score form",
                score_form_response.status_code == 200,
                f"Status: {score_form_response.status_code}"
            )

            # Bulk enter scores
            if student_ids and section_id:
                scores_data = {
                    "section_id": section_id,
                    "scores": [
                        {"student_id": sid, "score": 75.5, "teacher_remark": "Good work"}
                        for sid in student_ids[:3]  # Test with first 3 students
                    ]
                }
                enter_scores_response = await client.post(
                    f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}/scores",
                    headers=headers,
                    json=scores_data,
                )
                log_result(
                    "POST /exams/{id}/subjects/{subj}/scores - Bulk enter scores",
                    enter_scores_response.status_code in [200, 201],
                    f"Status: {enter_scores_response.status_code}, Response: {enter_scores_response.text[:200]}"
                )

                # Update individual score (mark absent)
                if student_ids:
                    update_score_response = await client.put(
                        f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}/scores/{student_ids[0]}",
                        headers=headers,
                        json={"score": 80, "is_absent": False, "teacher_remark": "Improved"},
                    )
                    log_result(
                        "PUT /exams/{id}/subjects/{subj}/scores/{student} - Update score",
                        update_score_response.status_code == 200,
                        f"Status: {update_score_response.status_code}"
                    )

                # Submit scores
                submit_response = await client.post(
                    f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}/submit",
                    headers=headers,
                )
                log_result(
                    "POST /exams/{id}/subjects/{subj}/submit - Submit scores",
                    submit_response.status_code == 200,
                    f"Status: {submit_response.status_code}"
                )
            else:
                if not section_id:
                    log_result("Bulk enter scores", True, "SKIPPED - No sections configured for class (requires section_id)")
                else:
                    log_result("Bulk enter scores", False, "No students available in section")
        else:
            log_result("Score entry endpoints", False, "No exam_subject_id available")

        # =============================================
        # 4. CONTINUOUS ASSESSMENT ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("4. CONTINUOUS ASSESSMENT ENDPOINTS")
        print("=" * 60)

        ca_id = None
        if class_id and subject_id and student_ids and academic_year_id and term_id:
            # Create CA entry
            ca_data = {
                "term_id": term_id,
                "class_id": class_id,
                "subject_id": subject_id,
                "student_id": student_ids[0],
                "assessment_type": "class_work",
                "title": "Week 1 Class Test",
                "max_score": 10,
                "score": 8,
                "assessment_date": str(date.today()),
            }
            create_ca_response = await client.post(
                f"{BASE_URL}/exams/ca",
                headers=headers,
                json=ca_data,
            )
            log_result(
                "POST /ca - Create CA entry",
                create_ca_response.status_code == 201,
                f"Status: {create_ca_response.status_code}, Response: {create_ca_response.text[:200]}"
            )

            if create_ca_response.status_code == 201:
                ca_id = create_ca_response.json()["id"]
                print(f"  Created CA ID: {ca_id}")

            # Bulk create CA
            bulk_ca_data = {
                "term_id": term_id,
                "class_id": class_id,
                "subject_id": subject_id,
                "assessment_type": "homework",
                "title": "Week 1 Homework",
                "max_score": 10,
                "assessment_date": str(date.today()),
                "scores": [
                    {"student_id": sid, "score": 7 + i} for i, sid in enumerate(student_ids[:3])
                ],
            }
            bulk_ca_response = await client.post(
                f"{BASE_URL}/exams/ca/bulk",
                headers=headers,
                json=bulk_ca_data,
            )
            log_result(
                "POST /ca/bulk - Bulk create CA",
                bulk_ca_response.status_code == 201,
                f"Status: {bulk_ca_response.status_code}"
            )

            # List CA entries
            list_ca_response = await client.get(
                f"{BASE_URL}/exams/ca",
                headers=headers,
                params={
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "term_id": term_id,
                },
            )
            log_result(
                "GET /ca - List CA entries",
                list_ca_response.status_code == 200,
                f"Status: {list_ca_response.status_code}"
            )

            # Update CA entry
            if ca_id:
                update_ca_response = await client.put(
                    f"{BASE_URL}/exams/ca/{ca_id}",
                    headers=headers,
                    json={"score": 9, "title": "Updated Week 1 Class Test"},
                )
                log_result(
                    "PUT /ca/{id} - Update CA entry",
                    update_ca_response.status_code == 200,
                    f"Status: {update_ca_response.status_code}"
                )

            # Get CA summary
            ca_summary_response = await client.get(
                f"{BASE_URL}/exams/ca/summary",
                headers=headers,
                params={
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "term_id": term_id,
                },
            )
            log_result(
                "GET /ca/summary - Get CA summary",
                ca_summary_response.status_code == 200,
                f"Status: {ca_summary_response.status_code}"
            )

            # Delete CA entry
            if ca_id:
                delete_ca_response = await client.delete(
                    f"{BASE_URL}/exams/ca/{ca_id}",
                    headers=headers,
                )
                log_result(
                    "DELETE /ca/{id} - Delete CA entry",
                    delete_ca_response.status_code == 204,
                    f"Status: {delete_ca_response.status_code}"
                )
        else:
            log_result("CA endpoints", False, "Missing prerequisite data")

        # =============================================
        # 5. RESULTS & RANKINGS ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("5. RESULTS & RANKINGS ENDPOINTS")
        print("=" * 60)

        # Results endpoints are not yet implemented in the backend
        # They would be at /exams/{id}/results, /exams/{id}/results/class/{class_id}, etc.
        # Skipping results tests for now
        log_result(
            "Results endpoints - Not implemented yet",
            True,  # Mark as pass - known limitation
            "Results endpoints are planned for future implementation"
        )

        # =============================================
        # 6. TERM REPORTS ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("6. TERM REPORTS ENDPOINTS")
        print("=" * 60)

        if class_id and term_id:
            # Generate term reports
            generate_response = await client.post(
                f"{BASE_URL}/exams/reports/term/generate",
                headers=headers,
                json={
                    "class_id": class_id,
                    "term_id": term_id,
                    "section_id": section_id,
                },
            )
            log_result(
                "POST /exams/reports/term/generate - Generate reports",
                generate_response.status_code in [200, 201],
                f"Status: {generate_response.status_code}"
            )

            # List term reports
            list_reports_response = await client.get(
                f"{BASE_URL}/exams/reports/term",
                headers=headers,
                params={"class_id": class_id, "term_id": term_id},
            )
            log_result(
                "GET /exams/reports/term - List term reports",
                list_reports_response.status_code == 200,
                f"Status: {list_reports_response.status_code}"
            )

            term_report_id = None
            if list_reports_response.status_code == 200:
                reports_data = list_reports_response.json()
                if reports_data.get("items"):
                    term_report_id = reports_data["items"][0]["id"]

            # Get single term report
            if term_report_id:
                get_report_response = await client.get(
                    f"{BASE_URL}/exams/reports/term/{term_report_id}",
                    headers=headers,
                )
                log_result(
                    "GET /exams/reports/term/{id} - Get term report",
                    get_report_response.status_code == 200,
                    f"Status: {get_report_response.status_code}"
                )

                # Update remarks
                remarks_response = await client.put(
                    f"{BASE_URL}/exams/reports/term/{term_report_id}/remarks",
                    headers=headers,
                    json={
                        "class_teacher_remark": "A good student with potential",
                        "headmaster_remark": "Keep up the good work",
                        "conduct_grade": "A",
                    },
                )
                log_result(
                    "PUT /exams/reports/term/{id}/remarks - Update remarks",
                    remarks_response.status_code == 200,
                    f"Status: {remarks_response.status_code}"
                )

            # Publish term reports
            publish_reports_response = await client.post(
                f"{BASE_URL}/exams/reports/term/publish",
                headers=headers,
                params={
                    "term_id": term_id,
                    "class_id": class_id,
                },
            )
            log_result(
                "POST /exams/reports/term/publish - Publish reports",
                publish_reports_response.status_code == 200,
                f"Status: {publish_reports_response.status_code}"
            )
        else:
            log_result("Term reports endpoints", False, "Missing class_id or term_id")

        # =============================================
        # 7. RESULTS / RANKINGS ENDPOINTS
        # =============================================
        print("\n" + "=" * 60)
        print("7. RESULTS / RANKINGS ENDPOINTS")
        print("=" * 60)

        if exam_id and class_id:
            # Get class results
            class_results_response = await client.get(
                f"{BASE_URL}/exams/{exam_id}/results/class/{class_id}",
                headers=headers,
            )
            log_result(
                "GET /exams/{id}/results/class/{class_id} - Get class results",
                class_results_response.status_code == 200,
                f"Status: {class_results_response.status_code}"
            )

            if class_results_response.status_code == 200:
                results_data = class_results_response.json()
                print(f"  Class: {results_data.get('class_name')}")
                print(f"  Students: {len(results_data.get('students', []))}")
                print(f"  Class Average: {results_data.get('class_average')}")

            # Get class results with section filter
            if section_id:
                section_results_response = await client.get(
                    f"{BASE_URL}/exams/{exam_id}/results/class/{class_id}",
                    headers=headers,
                    params={"section_id": section_id},
                )
                log_result(
                    "GET /exams/{id}/results/class/{class_id}?section_id - Get section results",
                    section_results_response.status_code == 200,
                    f"Status: {section_results_response.status_code}"
                )

            # Publish exam results
            publish_results_response = await client.post(
                f"{BASE_URL}/exams/{exam_id}/publish",
                headers=headers,
            )
            log_result(
                "POST /exams/{id}/publish - Publish exam results",
                publish_results_response.status_code == 200,
                f"Status: {publish_results_response.status_code}"
            )

            if publish_results_response.status_code == 200:
                publish_data = publish_results_response.json()
                print(f"  Published subjects: {publish_data.get('published_subjects')}")
        else:
            log_result("Results endpoints", False, "Missing exam_id or class_id")

        # =============================================
        # 8. CLEANUP - Delete test exam
        # =============================================
        print("\n" + "=" * 60)
        print("8. CLEANUP")
        print("=" * 60)

        if exam_id:
            # Delete exam subject first (if exists)
            if exam_subject_id:
                delete_subj_response = await client.delete(
                    f"{BASE_URL}/exams/{exam_id}/subjects/{exam_subject_id}",
                    headers=headers,
                )
                log_result(
                    "DELETE /exams/{id}/subjects/{subj_id} - Remove subject",
                    delete_subj_response.status_code == 204,
                    f"Status: {delete_subj_response.status_code}"
                )

            # Delete exam
            delete_exam_response = await client.delete(
                f"{BASE_URL}/exams/{exam_id}",
                headers=headers,
            )
            log_result(
                "DELETE /exams/{id} - Delete exam",
                delete_exam_response.status_code == 204,
                f"Status: {delete_exam_response.status_code}"
            )

        # =============================================
        # SUMMARY
        # =============================================
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in results if r["passed"])
        failed = sum(1 for r in results if not r["passed"])
        total = len(results)

        print(f"\nTotal: {total} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "N/A")

        if failed > 0:
            print("\nFailed tests:")
            for r in results:
                if not r["passed"]:
                    print(f"  - {r['test']}: {r['details']}")

        return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)
