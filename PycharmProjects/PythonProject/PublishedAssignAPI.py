# ============================================================================
# 4. Published Wordbook Assign APIs (시중 단어장 반/학생 출제)
# ============================================================================

@router.post("/{wordbook_id}/assign", response_model=WordbookAssignOut, status_code = status.HTTP_201_CREATED)
async def assign_wordbook(
        wordbook_id : str,
        target_type : str = Query(..., description = "출제 대상 타입 (class 또는 student)"),
        target_ids : List[int] = Query(..., description = "출제 대상 ID 목록"),
        academy_id : int = Query(..., description = "학원 ID"),
        user = Depends(require_user),
        sb : Client = Depends(get_supabase_client_with_token),
):
    """
    Assign wordbook to class or student (단어장 반/학생 출제)
    - 반 또는 학생에게 시중 단어장 출제
    """

    # 학원 소유자 확인
    _verify_academy_owner(sb, user.id, academy_id)

    try:
        # 단어장 확인
        wordbook_result = (
            sb.schema("attendance")
            .table("published_wordbooks")
            .select("wordbook_id, wordbook_title")
            .eq("wordbook_id", wordbook_id)
            .eq("is_active", True)
            .execute()
        )

        if not wordbook_result.data:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = "단어장을 찾을 수 없습니다."
            )

        # 학생 ID 추출
        student_ids = _get_student_ids_from_targets(sb, target_type, target_ids)

        if not student_ids:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "출제 대상 학생이 없습니다."
            )

        existing_result = (
            sb.schema("attendance")
            .table("published_wordbook_assignments")
            .select("student_id, assignment_number")
            .eq("wordbook_id", wordbook_id)
            .in_("student_id", student_ids)
            .execute()
        )

        #assignment_number 계산
        max_assignment_by_student ={}
        for row in existing_result.data:
            si = row ["student_id"]
            max_assignment_by_student[si]=max(max_assignment_by_student.get(si,0), row["assignment_number"])


        new_assignments = [
            {
                "wordbook_id" : wordbook_id,
                "student_id" : student_id,
                "academy_id" : academy_id,
                "status" : "assigned",
                "assignment_number": max_assignment_by_student.get(student_id,0) + 1,
            }
            for student_id in student_ids

        ]

        if new_assignments:
            sb.schema("attendance").table("published_wordbook_assignments").insert(new_assignments).execute()

        return {
            "success" : True,
            "message" : f"{len(student_ids)} 명의 학생에게 단어장이 출제되었습니다.",
            "student_count" : len(student_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"단어장 출제 중 오류가 발생했습니다. : {str(e)}"
        )