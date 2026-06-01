
import "./controlpanel.css"
import Footer from "../components/footer";
import Tab from "../components/tab";
import Button from "../components/Button";
import LoadingSpinner from "../components/LoadingSpinner";
//https://www.svgrepo.com/svg/529282/user-hand-up -- color changes
import studentdark from "../assets/student-dark.svg"
//https://www.svgrepo.com/svg/529282/user-hand-up -- color changes
import studentlight from "../assets/student-light.svg"
//https://www.svgrepo.com/svg/529046/library -- color changes
import coursesdark from "../assets/courses-dark.svg"
//https://www.svgrepo.com/svg/529046/library -- color changes
import courseslight from "../assets/courses-light.svg"
//https://www.svgrepo.com/svg/529151/question-square -- color changes
import questiondark from "../assets/question-dark.svg"
//https://www.svgrepo.com/svg/529151/question-square -- color changes
import questionlight from "../assets/question-light.svg"
//https://www.svgrepo.com/svg/529235/star-shine -- color changes
import stardark from "../assets/star-dark.svg"
//https://www.svgrepo.com/svg/529235/star-shine -- color changes
import starlight from "../assets/star-light.svg"
//https://www.svgrepo.com/svg/528832/add-circle
import add from "../assets/add.svg"
//https://www.svgrepo.com/svg/529234/square-top-up
import edit from "../assets/edit.svg"
//https://www.svgrepo.com/svg/528848/archive-up
import archiveup from "../assets/archive-up.svg"
//https://www.svgrepo.com/svg/528912/close-circle
import exit from "../assets/exit.svg"
//https://www.svgrepo.com/svg/528912/close-circle -- color changes
import exit_dark from "../assets/exit-dark.svg"
//https://www.svgrepo.com/svg/528846/archive-down
import archivedown from "../assets/archive-down.svg"
//https://www.svgrepo.com/svg/529799/refresh
import refresh from "../assets/refresh.svg"
//https://www.svgrepo.com/svg/528907/clipboard-remove
import deleteaccount from "../assets/deleteaccount.svg"
//https://www.svgrepo.com/svg/528917/copy
import copy from "../assets/copy.svg"
//https://www.svgrepo.com/svg/529148/question-circle
import question from "../assets/questionmark.svg"
//https://www.svgrepo.com/svg/529148/question-circle -- color changes
import question_dark from "../assets/questionmark-dark.svg"
import { DarkModeContext } from "../context/DarkModeContext";
import { Fragment, useContext, useDeferredValue, useState, useEffect, useRef, type ReactNode } from "react";
import type { courses, courseData } from "./questionselect";
import { MoreVertical, Power, Search, Trash2 } from "lucide-react";
import { canManageUsers, getCurrentBackendUser } from "../services/entraAuth";
import { apiFetch } from "../services/apt";
import { useScreenWidth } from "../services/screenwidth";
import { accColor } from "./history";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
// from https://www.npmjs.com/package/react-multi-select-component MIT License
import { MultiSelect } from "react-multi-select-component";
import { type Option } from "./questionselect";

interface Course {
    course_code: string;
    id: number;
    name: string;
}

interface Question {
    id: number;
    question_number: number;
    excerpt: string;
    active: boolean;
}

interface Category {
    active: boolean;
    id: number;
    name: string;
    courses: Course[];
    questions: Question[];
    down?: boolean;
}

interface FullCourse {
    id: number;
    course_code: string;
    name: string;
    active: boolean;
    created_at: string;
    last_updated: string;
    history: string;
}

interface FullCategory {
    id: number;
    name: string;
    active: boolean;
    created_at: string;
    last_updated: string;
    history: string;
}

interface FullQuestion {
    id: string;
    template: string;
    variables: Record<string, unknown>;
    formula: string;
    unit: string;
    tolerance: number | null;
    hints: string[];
    link: string;
    active: boolean;
    answer_type?: string;
    answer_min?: number;
    answer_max?: number;
    round_answer?: boolean;
    round_to_unit?: string;
}

interface UnitAlias {
    id: number;
    alias: string;
}

interface FullUnit {
    id: number;
    name: string;
    active: boolean;
    created_at: string;
    last_updated: string;
    aliases: UnitAlias[];
}

interface Variable {
    name: string;
    type: number;
    min: number | null;
    max: number | null;
    decimals: number | null;
    step: number | null;
    arr: string[] | null;
    depends_on: string[] | null;
    formula: string | null;
    names: string[] | string | null;

}

type AdminUser = {
    id: number;
    email: string;
    role: "Student" | "Admin";
    is_deactivated?: boolean;
}

type AdminUsers = {
    students: AdminUser[];
    admins: AdminUser[];
}

type AdminUserCounts = {
    students: number;
    admins: number;
    super_admins: number;
    total_users: number;
}

interface Period {
  from: string;
  to: string;
}

interface AdminOverviewStats {
  period: Period;
  total_sessions: number;
  total_questions_answered: number;
  total_correct: number;
  overall_accuracy_pct: number | null;
  active_courses: number;
  active_categories: number;
}

interface AdminCourseStats {
  course_id: number;
  course_code: string;
  course_name: string;
  session_count: number;
  questions_answered: number;
  correct_count: number;
  accuracy_pct: number | null;
  avg_score: number | null;
}

interface AdminCoursesResponse {
  period: Period;
  courses: AdminCourseStats[];
}

interface LinkedCourse {
  course_id: number;
  course_code: string;
  course_name: string;
}

interface AdminCategoryStats {
  category_id: number;
  category_name: string;
  session_count: number;
  questions_answered: number;
  correct_count: number;
  accuracy_pct: number | null;
  avg_score: number | null;
  linked_courses: LinkedCourse[];
}

interface AdminCategoriesResponse {
  period: Period;
  categories: AdminCategoryStats[];
}

type QuestionDifficulty = "easy" | "medium" | "hard";

interface QuestionCategory {
  category_id: number;
  name: string;
}

interface QuestionCourse {
  course_id: number;
  course_code: string;
  name: string;
}

interface AdminQuestionStats {
  template_id: string;
  template_text: string | null;
  unit: string | null;
  attempt_count: number;
  correct_count: number;
  accuracy_pct: number | null;
  difficulty: QuestionDifficulty;
  categories: QuestionCategory[];
  courses: QuestionCourse[];
}

interface AdminQuestionsResponse {
  period: Period;
  questions: AdminQuestionStats[];
}

interface BaseStatsQuery {
  from_date?: string;
  to_date?: string;
}

interface CategoryStatsQuery extends BaseStatsQuery {
  course_id?: number;
}

type QuestionSortBy = "accuracy" | "attempts";

interface QuestionStatsQuery extends BaseStatsQuery {
  course_id?: number;
  category_id?: number;
  sort_by?: QuestionSortBy;
  limit?: number;
}

interface AdminStatistics {
    overview: AdminOverviewStats;
    courses: AdminCoursesResponse;
    categories: AdminCategoriesResponse;
    questions: AdminQuestionsResponse;
}

async function getAdminStats(params?: QuestionStatsQuery): Promise<AdminStatistics> {

    const query = new URLSearchParams();

    if (params?.from_date)
        query.append("from_date", params.from_date);

    if (params?.to_date)
        query.append("to_date", params.to_date);

    if (params?.course_id)
        query.append("course_id", String(params.course_id));

    if (params?.category_id)
        query.append("category_id", String(params.category_id));

    if (params?.sort_by)
        query.append("sort_by", params.sort_by);

    if (params?.limit)
        query.append("limit", String(params.limit));

    const qs = query.toString() ? `?${query.toString()}` : "";
    const [
        overviewRes,
        coursesRes,
        categoriesRes,
        questionsRes
    ] = await Promise.all([
        fetch(`/api/admin/stats/overview${qs}`, {
            credentials: "include",
        }),

        fetch(`/api/admin/stats/courses${qs}`, {
            credentials: "include",
        }),

        fetch(`/api/admin/stats/categories${qs}`, {
            credentials: "include",
        }),

        fetch(`/api/admin/stats/questions${qs}`, {
            credentials: "include",
        }),
    ]);

    if (
        !overviewRes.ok ||
        !coursesRes.ok ||
        !categoriesRes.ok ||
        !questionsRes.ok
    ) {
        throw new Error("Failed to fetch admin stats");
    }

    const overview =
        await overviewRes.json() as AdminOverviewStats;

    const courses =
        await coursesRes.json() as AdminCoursesResponse;

    const categories =
        await categoriesRes.json() as AdminCategoriesResponse;

    const questions =
        await questionsRes.json() as AdminQuestionsResponse;

    return {
        overview,
        courses,
        categories,
        questions,
    };
}

export default function controlpanel(){
    const ctx = useContext(DarkModeContext)
    if (!ctx) return null;
    const { darkMode } = ctx
    const [tab, setTab] = useState(0);
    const [selectedCourse, setSelectedCourse] = useState<string>("");
    const [courses, setCourses] = useState<courses | null>(null);
    const [categories, setCategories] = useState<Category[] | null>(null);
    const [units, setUnits] = useState<FullUnit[] | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [viewing, setViewing] = useState<boolean | null>(null);
    // viewingType: 0 = course, 1 = category, 2 = question, 3 = unit, 4 = new course, 5 = new category, 6 = new question, 7 = new unit
    const [viewingType, setViewingType] = useState<number | null>(null);
    const [viewingData, setViewingData] = useState<FullCourse | FullCategory | FullQuestion | FullUnit | null>(null);
    const [categoryToAddQuestionTo, setCategoryToAddQuestionTo] = useState<Category | null>(null);

    // question input states
    const [questionText, setQuestionText] = useState<string>("");
    const [questionFormula, setQuestionFormula] = useState<string>("");
    const [questionUnit, setQuestionUnit] = useState<string>("");
    const [questionTolerance, setQuestionTolerance] = useState<string>("");
    const [questionAnswerType, setQuestionAnswerType] = useState<string>("numeric");
    const [questionRoundAnswer, setQuestionRoundAnswer] = useState<boolean>(false);
    const [questionRoundAnswerTime, setQuestionRoundAnswerTime] = useState<string>("min");
    const [questionAnswerMin, setQuestionAnswerMin] = useState<string>("");
    const [questionAnswerMax, setQuestionAnswerMax] = useState<string>("");
    const [, setQuestionVariables] = useState<Record<string, unknown>>({});
    const [questionHints, setQuestionHints] = useState<string[]>([]);
    const [questionLink, setQuestionLink] = useState<string>("");

    // course input states
    const [courseID, setCourseID] = useState<number>();
    const [courseName, setCourseName] = useState<string>("");
    const [courseCode, setCourseCode] = useState<string>("");
    const [courseActive, setCourseActive] = useState<boolean>(true);
    const [fullCourses, setFullCourses] = useState<FullCourse[] | null>([]);
 
    // category input states
    const [categoryID, setCategoryID] = useState<number | undefined>(undefined);
    const [categoryName, setCategoryName] = useState<string>("");
    const [categoryActive, setCategoryActive] = useState<boolean>(true);
    // const [selectedCourseIds, setSelectedCourseIds] = useState<number[]>([]);
    const [options, setOptions] = useState<Option[]>([]);
    const [selectedCourses, setSelected] = useState<Option[]>([]);

    // unit input states
    const [unitId, setUnitId] = useState<number>();
    const [unitName, setUnitName] = useState<string>("");
    const [unitActive, setUnitActive] = useState<boolean>(true);
    const [unitAliases, setUnitAliases] = useState<UnitAlias[]>([]);
    const [deletedUnitAliasIds, setDeletedUnitAliasIds] = useState<number[]>([]);
    

    const [variables, setVariables] = useState<Variable[]>([]);

    const [variableTab, setVariableTab] = useState<number[]>(Array(9999).fill(0));
    const [sampledValues, setSampledValues] = useState<Record<string, string | number>>({});
    const [adminUsers, setAdminUsers] = useState<AdminUsers>({ students: [], admins: [] });
    const [adminUserCounts, setAdminUserCounts] = useState<AdminUserCounts>({
        students: 0,
        admins: 0,
        super_admins: 0,
        total_users: 0,
    });
    const [adminUsersLoading, setAdminUsersLoading] = useState(false);
    const [adminUsersError, setAdminUsersError] = useState<string | null>(null);
    const [openRoleMenuUserId, setOpenRoleMenuUserId] = useState<number | null>(null);
    const [updatingRoleUserId, setUpdatingRoleUserId] = useState<number | null>(null);
    const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
    const [activatingUserId, setActivatingUserId] = useState<number | null>(null);
    const [deleteUserConfirm, setDeleteUserConfirm] = useState<AdminUser | null>(null);
    const [deleteUserError, setDeleteUserError] = useState<string | null>(null);
    const [adminUserActionError, setAdminUserActionError] = useState<string | null>(null);
    const [canManageUserRoles, setCanManageUserRoles] = useState(false);
    const [studentSearchQuery, setStudentSearchQuery] = useState("");
    const [adminSearchQuery, setAdminSearchQuery] = useState("");
    const deferredStudentSearchQuery = useDeferredValue(studentSearchQuery);
    const deferredAdminSearchQuery = useDeferredValue(adminSearchQuery);
    const deleteUserDescriptionStart = "Det h\u00e4r avaktiverar kontot f\u00f6r";
    const deleteUserDescriptionEnd =
        "och tar bort sparade sessioner. \u00c4r du s\u00e4ker p\u00e5 att du vill forts\u00e4tta?";
    const searchPlaceholder = "S\u00f6k";
    const noUsersMessage = "Inga anv\u00e4ndare";
    const noMatchesMessage = "Inga tr\u00e4ffar";
    const width = useScreenWidth();
    const scrollRef = useRef(0);
    const [showduppopup, setShowDupPopup] = useState<boolean>(false);
    const [dupq, setdupq] = useState<Question | null>()
    const [dupcat, setdupcat] = useState<Category | null>()
    const [seeArchive, setSeeArchive] = useState<boolean>(false)
    const [adminStats, setAdminStats] = useState<AdminStatistics | null>(null);


    async function get_courses_and_categories(): Promise<courses | null> {
        try {
            const res = await apiFetch("/api/categories");
            if (!res.ok) throw new Error(`/api/categories returned ${res.status}`);
            const json = await res.json();
            console.log(json);
            return json;
        } catch (error) {
            console.error("Error fetching courses and categories:", error);
            return null;
        }
    }

    async function get_full_categories(): Promise<Category[] | null> {
        try {
            const res = await apiFetch("/api/admin/categories");
            const json = await res.json();
            console.log("Categories:", json);
            return json;
        } catch (error) {
            console.error("Error fetching categories:", error);
            return null;
        }
    }

    async function get_full_units(): Promise<FullUnit[] | null> {
        try {
            const res = await apiFetch("/api/admin/units");
            const json = await res.json();
            console.log("Units:", json);
            return json;
        } catch (error) {
            console.error("Error fetching units:", error);
            return null;
        }
    }
    async function get_admin_statistics(params?: QuestionStatsQuery): Promise<void> {
        try {
            const statistics = await getAdminStats(params);
            setAdminStats(statistics);
        } catch (error) {
            console.error("Error fetching admin stats:", error);
        }
    }
    async function get_full_courses(): Promise<FullCourse[] | null> {
        try {
            const res = await apiFetch("/api/admin/courses")
            const json = await res.json();
            console.log("Course info:", json)
            return json;
        } catch (error) {
            console.error("Error fetching course info:", error);
            return null;
        }
    }

    async function fetchData() {
        scrollRef.current = window.scrollY;
        setIsLoading(true);
        try {
            const courses = await get_courses_and_categories();
            setCourses(courses);
            const categories = await get_full_categories();
            setCategories((prevCategories) => {
                if (!categories) return null;
                return categories.map((newCat) => {
                    const existingCat = prevCategories?.find((cat) => cat.id === newCat.id);
                    return {
                        ...newCat,
                        down: existingCat?.down ?? false,
                    };
                });
            });
            const units = await get_full_units();
            setUnits(units);
            const full_courses = await get_full_courses();
            setFullCourses(full_courses);
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        if (!isLoading) {
            window.scrollTo(0, scrollRef.current);
        }
    }, [isLoading]);

    useEffect(() => {
        console.log(adminStats)
    }, [adminStats])

    useEffect(() => {
        fetchData();
    }, []);

    useEffect(() => {
        let ignore = false;

        async function fetchAdminUserCounts(){
            try {
                const res = await apiFetch("/api/admin/user-counts");

                if(!res.ok){
                    throw new Error("Could not fetch admin user counts");
                }

                const json = await res.json() as Partial<AdminUserCounts>;
                if(!ignore){
                    setAdminUserCounts({
                        students: typeof json.students === "number" ? json.students : 0,
                        admins: typeof json.admins === "number" ? json.admins : 0,
                        super_admins: typeof json.super_admins === "number" ? json.super_admins : 0,
                        total_users: typeof json.total_users === "number" ? json.total_users : 0,
                    });
                }
            } catch (error) {
                console.error("Could not fetch admin user counts:", error);
            }
        }

        async function fetchPermissions(){
            try {
                const user = await getCurrentBackendUser();
                if(!ignore){
                    setCanManageUserRoles(Boolean(user?.can_manage_users || canManageUsers(user?.role)));
                }
            } catch {
                if(!ignore){
                    setCanManageUserRoles(false);
                }
            }
        }

        void fetchAdminUserCounts();
        void fetchPermissions();

        return () => {
            ignore = true;
        }
    }, []);

    useEffect(() => {
        if(!canManageUserRoles && tab === 3){
            setTab(0);
        }
    }, [canManageUserRoles, tab]);

    useEffect(() => {
        if(tab !== 3 || !canManageUserRoles){
            return;
        }

        let ignore = false;

        async function fetchAdminUsers() {
            setAdminUsersLoading(true);
            setAdminUsersError(null);

            try {
                const res = await apiFetch("/api/admin/users?limit=200");

                if(!res.ok){
                    throw new Error("Could not fetch admin users");
                }

                const json = await res.json() as AdminUsers;
                if(!ignore){
                    const nextStudents = Array.isArray(json.students) ? json.students : [];
                    const nextAdmins = Array.isArray(json.admins) ? json.admins : [];
                    setAdminUsers({
                        students: sort_admin_users(nextStudents),
                        admins: sort_admin_users(nextAdmins),
                    });
                    setAdminUserCounts((current) => ({
                        ...current,
                        students: count_active_admin_users(nextStudents),
                        admins: count_active_admin_users(nextAdmins),
                        total_users: count_active_admin_users(nextStudents) + count_active_admin_users(nextAdmins) + current.super_admins,
                    }));
                }
            } catch {
                if(!ignore){
                    setAdminUsersError("Kunde inte h\u00e4mta anv\u00e4ndare");
                }
            } finally {
                if(!ignore){
                    setAdminUsersLoading(false);
                }
            }
        }

        fetchAdminUsers();

        return () => {
            ignore = true;
        }
    }, [tab, canManageUserRoles]);

    useEffect(() => {
        function closeRoleMenu(){
            setOpenRoleMenuUserId(null);
        }

        document.addEventListener("click", closeRoleMenu);

        return () => {
            document.removeEventListener("click", closeRoleMenu);
        }
    }, []);

    useEffect(() => {
        if (viewingType === 2 && viewingData) {
            const questionData = viewingData as FullQuestion;
            setQuestionText(questionData.template || "");
            setQuestionFormula(questionData.formula || "");
            setQuestionUnit(questionData.unit || "");
            setQuestionTolerance(questionData.tolerance?.toString() || "");
            setQuestionAnswerType(questionData.answer_type || "numeric");
            setQuestionRoundAnswer(questionData.round_answer || false);
            setQuestionRoundAnswerTime(questionData.round_to_unit || "min");
            setQuestionAnswerMin(questionData.answer_min !== undefined && questionData.answer_min !== null ? questionData.answer_min.toString() : "");
            setQuestionAnswerMax(questionData.answer_max !== undefined && questionData.answer_max !== null ? questionData.answer_max.toString() : "");
            setQuestionVariables(questionData.variables || {});
            setQuestionHints(questionData.hints || []);
            setQuestionLink(questionData.link || "");
            // Load existing variables from the question data
            if (questionData.variables && typeof questionData.variables === 'object') {
                // Convert Record to Variable array
                const loadedVariables = Object.entries(questionData.variables).map(
                    ([name, data]: [string, any]) => {

                        let type = 3;

                        if (data?.arr && Array.isArray(data.arr)) {
                            type = 1; // list type
                        } else if (Array.isArray(data) && (data.length === 0 || typeof data[0] === 'number')) {
                            type = 1; // plain numeric array e.g. [20]
                        } else if (typeof data === 'string' || (Array.isArray(data) && typeof data[0] === 'string')) {
                            type = 3; // name type
                        } else if (data?.formula) {
                            type = 2; // formula type
                        } else if (data?.min != null || data?.max != null) {
                            type = 0; // range type
                        }

                        return {
                            name,
                            type,
                            min: data?.min ?? null,
                            max: data?.max ?? null,
                            decimals: data?.decimals ?? null,
                            step: data?.step ?? null,

                            arr: Array.isArray(data?.arr)
                                ? data.arr.map(String)
                                : Array.isArray(data) && (data.length === 0 || typeof data[0] === 'number')
                                    ? (data as number[]).map(String)
                                    : null,

                            depends_on: data?.depends_on
                                ? Array.isArray(data.depends_on)
                                    ? data.depends_on
                                    : [data.depends_on]
                                : null,

                            formula: data?.formula ?? null,

                            names:
                                typeof data === 'string'
                                    ? data
                                    : Array.isArray(data) && typeof data[0] === 'string'
                                        ? data
                                        : null,
                        };
                    }
                    );
                console.log("Loaded variables from data:", loadedVariables);
                setVariables(loadedVariables);
                const newTab = Array(9999).fill(0);

                loadedVariables.forEach((v, i) => {
                    newTab[i] = v.type; // assign type at same index
                });

                setVariableTab(newTab);
            } else {
                setVariables([]);
                setVariableTab(Array(9999).fill(0));
            }
        } else if (viewingType === 6) {
            // Reset form for new question
            setQuestionText("");
            setQuestionFormula("");
            setQuestionUnit("");
            setQuestionTolerance("");
            setQuestionAnswerType("numeric");
            setQuestionRoundAnswer(false);
            setQuestionAnswerMin("");
            setQuestionAnswerMax("");
            setQuestionVariables({});
            setQuestionHints([]);
            setQuestionLink("");
            setVariables([]);
        } else if (viewingType === 0 && viewingData) {
            const courseData = viewingData as FullCourse;
            setCourseName(courseData.name || "");
            setCourseCode(courseData.course_code || "");
            setCourseActive(courseData.active || true);
            setCourseID(courseData.id || -1)
        } else if (viewingType === 4) {
            // Reset form for new course
            setCourseName("");
            setCourseCode("");
            setCourseActive(true);
            setCourseID(undefined);
        } else if (viewingType === 1 && viewingData) {
            const categoryData = viewingData as FullCategory;
            setCategoryID(categoryData.id);
            setCategoryName(categoryData.name || "");
            setCategoryActive(categoryData.active ?? true);
            const existingCat = categories?.find(c => c.id === categoryData.id);
            setSelected(existingCat?.courses.map(c => ({
                label: `${c.course_code} - ${c.name}`,
                value: c.id.toString(),
            })) ?? []);
            setOptions(fullCourses?.map((c) => (
            {
                label: `${c.course_code} - ${c.name}`,
                value: c.id.toString(),
            })) ?? []);
        } else if (viewingType === 5) {
            setCategoryID(undefined);
            setCategoryName("");
            setCategoryActive(true);
            setSelected([]);
            setOptions(fullCourses?.map((c) => (
            {
                label: `${c.course_code} - ${c.name}`,
                value: c.id.toString(),
            })) ?? []);
        } else if (viewingType === 3 && viewingData) {
            const unitData = viewingData as FullUnit;

            setUnitId(unitData.id);
            setUnitName(unitData.name || "");
            setUnitActive(unitData.active ?? true);
            setUnitAliases(unitData.aliases || []);
            setDeletedUnitAliasIds([]);
        } else if (viewingType === 7) {
            setUnitId(undefined);
            setUnitName("");
            setUnitActive(true);
            setUnitAliases([]);
            setDeletedUnitAliasIds([]);
            
        }
    }, [viewingData, viewingType]);

    function get_course_question_count(course: string, data: courses): number {
        if (!data.max_questions?.[course]) return 0;
        return Object.values(data.max_questions[course]).reduce((sum, count) => sum + count, 0);
    }

    function sort_admin_users(users: AdminUser[]){
        return [...users].sort((a, b) => {
            const deactivatedOrder = Number(Boolean(a.is_deactivated)) - Number(Boolean(b.is_deactivated));
            if(deactivatedOrder !== 0){
                return deactivatedOrder;
            }
            return a.email.localeCompare(b.email);
        });
    }

    function count_active_admin_users(users: AdminUser[]){
        return users.filter((user) => !user.is_deactivated).length;
    }

    function filter_admin_users(users: AdminUser[], query: string){
        const normalizedQuery = query.trim().toLowerCase();
        if(!normalizedQuery){
            return users;
        }

        return users.filter((user) => user.email.toLowerCase().includes(normalizedQuery));
    }

    async function update_user_role(user: AdminUser, role: "Student" | "Admin"){
        if(!canManageUserRoles || user.is_deactivated){
            return;
        }

        setUpdatingRoleUserId(user.id);
        setAdminUserActionError(null);

        try {
            const res = await apiFetch(`/api/admin/users/${user.id}/role`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role }),
            });

            if(!res.ok){
                throw new Error("Could not update user role");
            }

            const updatedUser = await res.json() as AdminUser;
            setAdminUsers((current) => {
                const students = current.students.filter((candidate) => candidate.id !== updatedUser.id);
                const admins = current.admins.filter((candidate) => candidate.id !== updatedUser.id);

                if(updatedUser.role === "Student"){
                    students.push(updatedUser);
                } else {
                    admins.push(updatedUser);
                }

                return {
                    students: sort_admin_users(students),
                    admins: sort_admin_users(admins),
                };
            });
            setAdminUserCounts((current) => {
                if(user.role === updatedUser.role){
                    return current;
                }

                return {
                    ...current,
                    students: updatedUser.role === "Student"
                        ? current.students + 1
                        : Math.max(0, current.students - 1),
                    admins: updatedUser.role === "Admin"
                        ? current.admins + 1
                        : Math.max(0, current.admins - 1),
                };
            });
            setOpenRoleMenuUserId(null);
        } catch (error) {
            console.error("Could not update user role:", error);
        } finally {
            setUpdatingRoleUserId(null);
        }
    }

    async function deactivate_admin_user(user: AdminUser){
        if(!canManageUserRoles){
            return;
        }

        setDeletingUserId(user.id);
        setDeleteUserError(null);
        setAdminUserActionError(null);

        try {
            const res = await apiFetch(`/api/admin/users/${user.id}`, {
                method: "DELETE",
            });

            if(!res.ok){
                const payload = await res.json().catch(() => null);
                const message =
                    payload &&
                    typeof payload === "object" &&
                    "error" in payload &&
                    typeof payload.error === "string"
                        ? payload.error
                        : "Kunde inte avaktivera anv\u00e4ndaren.";
                throw new Error(message);
            }

            setAdminUsers((current) => ({
                students: sort_admin_users(
                    current.students.map((candidate) =>
                        candidate.id === user.id
                            ? { ...candidate, is_deactivated: true }
                            : candidate
                    )
                ),
                admins: sort_admin_users(
                    current.admins.map((candidate) =>
                        candidate.id === user.id
                            ? { ...candidate, is_deactivated: true }
                            : candidate
                    )
                ),
            }));
            if(!user.is_deactivated){
                setAdminUserCounts((current) => ({
                    ...current,
                    students: user.role === "Student"
                        ? Math.max(0, current.students - 1)
                        : current.students,
                    admins: user.role === "Admin"
                        ? Math.max(0, current.admins - 1)
                        : current.admins,
                    total_users: Math.max(0, current.total_users - 1),
                }));
            }
            setDeleteUserConfirm(null);
            setOpenRoleMenuUserId(null);
        } catch (error) {
            console.error("Could not deactivate user:", error);
            setDeleteUserError(
                error instanceof Error && error.message.trim()
                    ? error.message
                    : "Kunde inte avaktivera anv\u00e4ndaren.",
            );
        } finally {
            setDeletingUserId(null);
        }
    }

    async function activate_admin_user(user: AdminUser){
        if(!canManageUserRoles || !user.is_deactivated){
            return;
        }

        setActivatingUserId(user.id);
        setAdminUserActionError(null);

        try {
            const res = await apiFetch(`/api/admin/users/${user.id}/activate`, {
                method: "PATCH",
            });

            if(!res.ok){
                const payload = await res.json().catch(() => null);
                const message =
                    payload &&
                    typeof payload === "object" &&
                    "error" in payload &&
                    typeof payload.error === "string"
                        ? payload.error
                        : "Kunde inte aktivera anv\u00e4ndaren.";
                throw new Error(message);
            }

            const payload = await res.json() as { user?: AdminUser };
            const activatedUser = payload.user ?? { ...user, is_deactivated: false };

            setAdminUsers((current) => ({
                students: sort_admin_users(
                    current.students.map((candidate) =>
                        candidate.id === user.id ? activatedUser : candidate
                    )
                ),
                admins: sort_admin_users(
                    current.admins.map((candidate) =>
                        candidate.id === user.id ? activatedUser : candidate
                    )
                ),
            }));
            setAdminUserCounts((current) => ({
                ...current,
                students: user.role === "Student"
                    ? current.students + 1
                    : current.students,
                admins: user.role === "Admin"
                    ? current.admins + 1
                    : current.admins,
                total_users: current.total_users + 1,
            }));
        } catch (error) {
            console.error("Could not activate user:", error);
            setAdminUserActionError(
                error instanceof Error && error.message.trim()
                    ? error.message
                    : "Kunde inte aktivera anv\u00e4ndaren.",
            );
        } finally {
            setActivatingUserId(null);
        }
    }

    function get_user_list(
        title: string,
        users: AdminUser[],
        actionLabel: string,
        nextRole: "Student" | "Admin",
        searchQuery: string,
        onSearchQueryChange: (query: string) => void,
    ){
        const filteredUsers = filter_admin_users(users, searchQuery);
        const emptyMessage = users.length === 0 ? noUsersMessage : noMatchesMessage;

        return(
            <section className="admin-user-list-frame">
                <div className="admin-user-list-header">
                    <h2>{title}</h2>
                    <span>{filteredUsers.length}</span>
                </div>
                <div className="admin-user-list">
                    <label className="admin-user-search-shell">
                        <Search size={18} strokeWidth={2.4} aria-hidden="true" />
                        <input
                            type="search"
                            value={searchQuery}
                            placeholder={searchPlaceholder}
                            onChange={(event) => onSearchQueryChange(event.target.value)}
                            aria-label={`S\u00f6k ${title.toLowerCase()}`}
                        />
                    </label>
                    {adminUsersLoading && <LoadingSpinner></LoadingSpinner>}
                    {!adminUsersLoading && adminUserActionError && (
                        <p className="admin-user-action-error">{adminUserActionError}</p>
                    )}
                    {!adminUsersLoading && adminUsersError && <p className="admin-user-list-message">{adminUsersError}</p>}
                    {!adminUsersLoading && !adminUsersError && filteredUsers.length === 0 && (
                        <p className="admin-user-list-message">{emptyMessage}</p>
                    )}
                    {!adminUsersLoading && !adminUsersError && filteredUsers.map((user) => (
                        <div
                            className={`admin-user-row${user.is_deactivated ? " admin-user-row-deactivated" : ""}`}
                            key={`${user.role}-${user.id}`}
                        >
                            <div className="admin-user-identity">
                                <span className="admin-user-email">{user.email}</span>
                                {user.is_deactivated ? (
                                    <span className="admin-user-status">Avaktiverad</span>
                                ) : null}
                            </div>
                            {user.is_deactivated ? (
                                <button
                                    className="admin-user-activate-button"
                                    type="button"
                                    onClick={() => void activate_admin_user(user)}
                                    disabled={activatingUserId === user.id}
                                    aria-label={`Aktivera konto f\u00f6r ${user.email}`}
                                >
                                    <Power size={15} strokeWidth={2.5} aria-hidden="true" />
                                    <span>{activatingUserId === user.id ? "Aktiverar..." : "Aktivera"}</span>
                                </button>
                            ) : (
                                <button
                                    className="admin-user-menu-button"
                                    type="button"
                                    aria-label="\u00d6ppna rollmeny"
                                    title="Rollmeny"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setOpenRoleMenuUserId((openUserId) => openUserId === user.id ? null : user.id);
                                    }}
                                >
                                    <MoreVertical size={22} strokeWidth={2.4} />
                                </button>
                            )}
                            {!user.is_deactivated && openRoleMenuUserId === user.id && (
                                <div className="admin-user-menu" onClick={(e) => e.stopPropagation()}>
                                    <button
                                        type="button"
                                        onClick={() => void update_user_role(user, nextRole)}
                                        disabled={updatingRoleUserId === user.id || deletingUserId === user.id}
                                    >
                                        {updatingRoleUserId === user.id ? "Sparar..." : actionLabel}
                                    </button>
                                    <button
                                        type="button"
                                        className="admin-user-menu-delete"
                                        onClick={() => {
                                            setOpenRoleMenuUserId(null);
                                            setDeleteUserError(null);
                                            setDeleteUserConfirm(user);
                                        }}
                                        disabled={updatingRoleUserId === user.id || deletingUserId === user.id}
                                    >
                                        <Trash2 size={16} strokeWidth={2.4} aria-hidden="true" />
                                        <span>Avaktivera konto</span>
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </section>
        )
    }

    function get_admin_users(){
        return(
            <div className="admin-users-panel">
                {get_user_list(
                    "Studenter",
                    adminUsers.students,
                    "Ge adminbeh\u00f6righet",
                    "Admin",
                    deferredStudentSearchQuery,
                    setStudentSearchQuery,
                )}
                {get_user_list(
                    "Admins",
                    adminUsers.admins,
                    "Ta bort adminbeh\u00f6righet",
                    "Student",
                    deferredAdminSearchQuery,
                    setAdminSearchQuery,
                )}
            </div>
        )
    }

    function get_stats(){
        const students = adminUserCounts.students;
        const courseCount = courses ? Object.keys(courses.courses).length : 0;
        const questionCount = categories ? categories.reduce((sum, cat) => sum + cat.questions.length, 0) : 0;
        const correct = adminStats?.overview.overall_accuracy_pct ? Math.round(adminStats?.overview.overall_accuracy_pct) : 0;

        return(
            <div className="general-stats">
                <div className="stat-panel">
                    <img src={darkMode ? studentdark : studentlight} alt="student" />
                    <div className="stat-panel-text">
                        <p>Studenter</p>
                        <span>{students}</span>
                    </div>
                </div>
                <div className="vl"></div>
                <div className="stat-panel">
                    <img src={darkMode ? coursesdark : courseslight} alt="courses" />
                    <div className="stat-panel-text">
                        <p>kurser</p>
                        <span>{courseCount}</span>
                    </div>
                </div>
                <div className="vl"></div>
                <div className="stat-panel">
                    <img src={darkMode ? questiondark : questionlight} alt="questions" />
                    <div className="stat-panel-text">
                        <p>Frågor</p>
                        <span>{questionCount}</span>
                    </div>
                </div>
                <div className="vl"></div>
                <div className="stat-panel">
                    <img src={darkMode ? stardark : starlight} alt="correct" />
                    <div className="stat-panel-text">
                        <p>rätt</p>
                        <span>{correct}%</span>
                    </div>
                </div>
            </div>
        )
    }

    function handle_category_expand(categoryId: number){
        setCategories((prevCategories) => {
            if (!prevCategories) return prevCategories;
            return prevCategories.map((category) =>
                category.id === categoryId
                    ? { ...category, down: !category.down }
                    : category
            );
        });
    }
    async function getEntity(type: number, id: string) {
        try {
            console.log(`Using route: /api/admin/entity/${type}/${id}`);
            const res = await apiFetch(`/api/admin/entity/${type}/${id}`);
            const json = await res.json();
            console.log("entity:", json);
            return json;
        } catch (error) {
            console.error("Error fetching entity:", error);
            return null;
        }
    }

    function openViewing(type: number, id: string | null){
        setViewing(true);
        setViewingType(type);
        if(id){
            getEntity(type, id).then(data => {
                setViewingData(data);
            });
        } else {
            switch(type){
                case 4:
                    setViewingData({
                        id: 0,
                        course_code: "",
                        name: "",
                        active: true,
                        created_at: null as any,
                        last_updated: null as any,
                        history: ""
                    });
                    break;
                case 5:
                    setViewingData({
                        id: 0,
                        name: "",
                        active: true,
                        created_at: null as any,
                        last_updated: null as any,
                        history: ""
                    });
                    break;
                case 6:
                    setViewingData({
                        id: "",
                        template: "",
                        variables: {},
                        formula: "",
                        unit: "",
                        tolerance: null,
                        hints: [],
                        link: "",
                        active: true
                    });
                    break;
                case 7:
                    setViewingData({
                        id: 0,
                        name: "",
                        active: true,
                        created_at: null as any,
                        last_updated: null as any,
                        aliases: []
                    });
                    break;
            }
        }
    }

    function closeViewing() {
        setViewing(null);
        setViewingType(null);
        setViewingData(null);
        
        // Reset question form
        setQuestionText("");
        setQuestionFormula("");
        setQuestionUnit("");
        setQuestionTolerance("");
        setQuestionAnswerType("numeric");
        setQuestionRoundAnswer(false);
        setQuestionAnswerMin("");
        setQuestionAnswerMax("");
        setQuestionVariables({});
        setQuestionHints([]);
        setQuestionLink("");
        setVariables([]);
        
        // Reset course form
        setCourseName("");
        setCourseCode("");
        setCourseActive(true);
        setCourseID(undefined);
        
        // Reset category form
        setCategoryName("");
        setCategoryActive(true);

        // Reset unit form
        setUnitActive(true);
        setUnitAliases([]);
        setUnitId(undefined);
        setUnitName("")
        setDeletedUnitAliasIds([]);


        if (window.history.state?.viewing) {
            window.history.back();
        }
    }

    async function mutate(operations: unknown[]) {
        const res = await apiFetch("/api/admin/mutate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(operations),
        });

        const data = await res.json();
        console.log("Mutation response:", data);

        if (!res.ok) {
            throw new Error(data.error || "Mutation failed");
        }

        if (data.results && data.results[0] && data.results[0].message) {
            throw new Error(data.results[0].message);
        }

        return data;
    }

    function variablesToBackendFormat() {
        const result: Record<string, unknown> = {};

        variables.forEach((variable) => {
            if (variable.type === 0) {
                result[variable.name] = {
                    min: variable.min,
                    max: variable.max,
                    step: variable.step,
                    decimals: variable.decimals,
                };
            } else if (variable.type === 1) {
                const values = (variable.arr ?? []).map(Number).filter(v => !isNaN(v));
                result[variable.name] = {
                    arr: variable.arr ?? [],
                    min: values.length ? Math.min(...values) : null,
                    max: values.length ? Math.max(...values) : null,
                };
            } else if (variable.type === 2) {
                result[variable.name] = {
                    formula: variable.formula,
                    depends_on: variable.depends_on,
                };
            } else if (variable.type === 3) {
                result[variable.name] = variable.names ?? "$STANDARD_NAMES";
            }
        });

        return result;
    }

    function validate_limits():boolean{
        let bad = 0;
        for(let i = 0; i < 100; i++){
            const result = eval_formula(questionFormula, sample_variables());
            if((questionAnswerMax != "" && result > questionAnswerMax) || (questionAnswerMin != "" && result < questionAnswerMin)) bad++;
        }
        return(bad < 25);
    }

    async function handleSaveCourse() {
        if (viewingType !== 4) return;

        const operation = {
            type: 0,
            action: 0,
            body: {
                course_code: courseCode || "",
                name: courseName || "",
                active: courseActive || true
            }
        };

        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(`Kunde inte spara kursen : ${error instanceof Error ? error.message : "Okänt fel från backend"}`);
        }
    }

    async function handleEditCourse() {
        if (viewingType !== 0) return;

        const operation = {
            type: 0,
            action: 2,
            body: {
                id: courseID || -1,
                course_code: courseCode || "",
                name: courseName || "",
                active: courseActive || true
            }
        };

        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(`Kunde inte spara kursen : ${error instanceof Error ? error.message : "Okänt fel från backend"}`);
        }
    }

    async function handleSaveCategory() {
        if (viewingType !== 5) return;
        const operation = {
            type: 1,
            action: 0,
            body: { name: categoryName, active: categoryActive, course_ids: selectedCourses.map((c) => c.value)}
        };
        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(`Kunde inte spara kategorin: ${error instanceof Error ? error.message : "Okänt fel från backend"}`);
        }
    }

    async function handleEditCategory() {
        if (viewingType !== 1 || !categoryID) return;

        const existingCat = categories?.find(c => c.id === categoryID);

        const existingCourseIds =
            existingCat?.courses.map((c) => c.id.toString()) ?? [];

        const selectedCourseIds = selectedCourses.map((c) => c.value);

        const selectedSet = new Set(selectedCourseIds);
        const existingSet = new Set(existingCourseIds);

        const add_course_ids = selectedCourseIds.filter(
            (id) => !existingSet.has(id)
        );

        const remove_course_ids = existingCourseIds.filter(
            (id) => !selectedSet.has(id)
        );

        const operation = {
            type: 1,
            action: 2,
            body: {
                id: categoryID,
                name: categoryName,
                active: categoryActive,
                add_course_ids,
                remove_course_ids,
            },
        };

        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(
                `Kunde inte spara kategorin: ${
                    error instanceof Error ? error.message : "Okänt fel från backend"
                }`
            );
        }
    }

    async function handleSaveQuestion() {
        if (!categoryToAddQuestionTo || viewingType !== 6) return;

        const operation = {
            type: 2,
            action: 0,
            body: {
                course_ids: categoryToAddQuestionTo.courses.map((course) => course.id),
                category_id: categoryToAddQuestionTo.id,
                template: questionText,
                variables: variablesToBackendFormat(),
                formula: questionFormula,
                unit: questionAnswerType === "duration" ? "" : questionUnit,
                tolerance: Number(questionTolerance) || 0,
                answer_type: questionAnswerType,
                round_answer: questionRoundAnswer,
                answer_min: questionAnswerMin ? parseFloat(questionAnswerMin) : null,
                answer_max: questionAnswerMax ? parseFloat(questionAnswerMax) : null,
                hints: questionHints,
                link: questionLink,
                active: true,
            }
        };
        if(!validate_limits()){

            alert("Frågan måste generera ett svar inom max och min gränserna minst 75% av gångerna för att frågan ska accepteras! Annars kan det bli fel för eleverna.");
            return
        }
        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(`Kunde inte spara frågan: ${error instanceof Error ? error.message : "Okänt fel från backend"}`);
        }
    }

    async function handleEditQuestion() {
        if (!categoryToAddQuestionTo || !viewingData || viewingType !== 2) return;

        const questionData = viewingData as FullQuestion;
        const operation = {
            type: 2,
            action: 2,
            body: {
                id: questionData.id,
                template: questionText,
                variables: variablesToBackendFormat(),
                formula: questionFormula,
                unit: questionAnswerType === "duration" ? "" : questionUnit,
                tolerance: questionTolerance.trim() == "" ? 0 : parseFloat(questionTolerance),
                answer_type: questionAnswerType,
                round_answer: questionRoundAnswer,
                answer_min: questionAnswerMin ? parseFloat(questionAnswerMin) : null,
                answer_max: questionAnswerMax ? parseFloat(questionAnswerMax) : null,
                hints: questionHints,
                link: questionLink,
            },
        };

        if(!validate_limits()){
            alert("Frågan måste generera ett svar inom max och min gränserna minst 75% av gångerna för att frågan ska accepteras! Annars kan det bli fel för eleverna.");
            return
        }

        try {
            await mutate([operation]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
            alert(`Kunde inte uppdatera frågan: ${error instanceof Error ? error.message : "Okänt fel från backend"}`);
        }
    }

    async function handleSaveUnit() {
        if (viewingType !== 7) return;

        const operations: unknown[] = [
            {
                type: 3,
                action: 0,
                body: {
                    name: unitName,
                    active: unitActive,
                }
            }
        ];

        try {
            const result = await mutate(operations);

            const newUnitId = result.results?.[0]?.id;

            if (newUnitId) {
                const aliasOperations = unitAliases
                    .filter(alias => alias.alias.trim() !== "")
                    .map(alias => ({
                        type: 4,
                        action: 0,
                        body: {
                            unit_id: newUnitId,
                            alias: alias.alias.trim(),
                        }
                    }));

                if (aliasOperations.length > 0) {
                    await mutate(aliasOperations);
                }
            }

            await fetchData();
            closeViewing();

        } catch (error) {
            console.error(error);

            alert(
                `Kunde inte spara enheten: ${
                    error instanceof Error
                        ? error.message
                        : "Okänt fel från backend"
                }`
            );
        }
    }

    async function handleEditUnit() {
        if (viewingType !== 3 || !unitId) return;

        try {
            // update unit itself
            await mutate([
                {
                    type: 3,
                    action: 2,
                    body: {
                        id: unitId,
                        name: unitName,
                        active: unitActive,
                    }
                }
            ]);

            const existingAliases = unitAliases.filter(
                alias => alias.id > 0
            );

            const newAliases = unitAliases.filter(
                alias => alias.id <= 0
            );

            const aliasOperations: unknown[] = [];

            // DELETE removed aliases
            aliasOperations.push(
                ...deletedUnitAliasIds.map(id => ({
                    type: 4,
                    action: 1,
                    body: {
                        id,
                    }
                }))
            );

            // EDIT existing aliases
            existingAliases.forEach(alias => {
                aliasOperations.push({
                    type: 4,
                    action: 2,
                    body: {
                        id: alias.id,
                        alias: alias.alias.trim(),
                    }
                });
            });

            // CREATE new aliases
            newAliases
                .filter(alias => alias.alias.trim() !== "")
                .forEach(alias => {
                    aliasOperations.push({
                        type: 4,
                        action: 0,
                        body: {
                            unit_id: unitId,
                            alias: alias.alias.trim(),
                        }
                    });
                });

            // run alias mutations
            if (aliasOperations.length > 0) {
                await mutate(aliasOperations);
            }

            setDeletedUnitAliasIds([]);

            await fetchData();

            closeViewing();

        } catch (error) {

            console.error(error);

            alert(
                `Kunde inte uppdatera enheten: ${
                    error instanceof Error
                        ? error.message
                        : "Okänt fel från backend"
                }`
            );
        }
    }

    async function handleArchive(type: number, id: string, active: boolean) {
        try {
            await mutate([{
                type,
                action: 1,
                body: {
                    id: parseInt(id, 10),
                    archive: active,
                },
            }]);
            await fetchData();
            closeViewing();
        } catch (error) {
            console.error(error);
        }
    }

    async function getFullQuestion(id: string): Promise<FullQuestion> {
        const res = await apiFetch(`/api/admin/entity/2/${id}`);
        return await res.json();
    }

    async function handleDuplicateQuestion(q: Question | null | undefined, cat: Category | null | undefined) {
        if(q == null || cat == null || q == undefined || cat == undefined) return;
        const full = await getFullQuestion(q.id.toString());
        console.log(full)
        const operation = {
            type: 2, // question
            action: 0, // create
            body: {
                course_ids: cat.courses.map(c => c.id),
                category_ids: [cat.id],
                template: full.template,
                variables: full.variables,
                formula: full.formula,
                unit: full.unit,
                tolerance: full.tolerance,
                answer_type: full.answer_type ?? "numeric",
                round_answer: full.round_answer ?? false,
                answer_min: full.answer_min ?? null,
                answer_max: full.answer_max ?? null,
                hints: full.hints ?? [],
                link: full.link ?? "",
                active: full.active,
            },
        };

        try {
            await mutate([operation]);
            setdupq(null);
            setdupq(null);
            await fetchData();
        } catch (err) {
            setdupq(null);
            setdupq(null);
            console.error("Duplicate failed:", err);
        }
    }

    function change_var_type(index: number, newType: number) {
        setVariables(prev => {
            const newVars = [...prev];
            const variable = newVars[index];
            if (!variable) return prev;
            variable.type = newType;
            return newVars;
        });
    }

    function get_var_chip_class(type: number): string {
        return ["var-chip-interval", "var-chip-lista", "var-chip-formel", "var-chip-namn", "var-chip-klockslag"][type] ?? "var-chip-interval";
    }

    useEffect(() => {
        setSampledValues(sample_variables());
    }, [variables]);

    function sample_variables(): Record<string, string | number> {
        const result: Record<string, string | number> = {};

        variables.forEach((variable) => {
            if (variable.type === 0) {
                const min = variable.min ?? 0;
                const max = variable.max ?? 100;
                const step = variable.step ?? 1;
                const decimals = variable.decimals ?? 0;
                const steps = Math.max(0, Math.floor((max - min) / step));
                const value = min + Math.floor(Math.random() * (steps + 1)) * step;
                result[variable.name] = parseFloat(value.toFixed(decimals));
            } else if (variable.type === 1) {
                const values = variable.arr ?? [];
                result[variable.name] = values[Math.floor(Math.random() * values.length)] ?? "";
            } else if (variable.type === 3) {
                const standardNames = ["Anna", "Erik", "Maria", "Johan", "Lisa"];
                const values = typeof variable.names === "string" ? standardNames : (variable.names ?? standardNames);
                result[variable.name] = values[Math.floor(Math.random() * values.length)] ?? "";
            }
        });

        variables.forEach((variable) => {
            if (variable.type === 2 && variable.formula) {
                try {
                    let expression = variable.formula;
                    Object.entries(result).forEach(([name, value]) => {
                        const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

                        expression = expression.replace(
                            new RegExp(`\\b${escaped}\\b`, 'g'),
                            String(value)
                        );
                    });
                    result[variable.name] = parseFloat(eval(expression).toFixed(variable.decimals ?? 0));
                } catch {
                    result[variable.name] = "?";
                }
            }
        });

        return result;
    }

    function roundSeconds(seconds: number, mode: string): number {
        const abs = Math.abs(seconds);

        switch (mode) {
            case "d": return Math.round(abs / 86400) * 86400;
            case "h": return Math.round(abs / 3600) * 3600;
            case "min": return Math.round(abs / 60) * 60;
            case "s": return Math.round(abs);
            default: return abs;
        }
    }

    function roundMinutes(minutes: number, mode: string): number {
        const abs = Math.abs(minutes);

        switch (mode) {
            case "d": return Math.round(abs / 1440) * 1440;
            case "h": return Math.round(abs / 60) * 60;
            case "min": return Math.round(abs);
            case "s": return Math.round(abs * 60) / 60;
            default: return abs;
        }
    }

    function format_duration_preview(seconds: number): string {
        if (!isFinite(seconds) || isNaN(seconds)) return "?";

        let rem = roundSeconds(seconds, questionRoundAnswerTime);
        const parts: string[] = [];

        if (rem >= 86400) { parts.push(`${Math.floor(rem / 86400)}d`); rem %= 86400; }
        if (rem >= 3600)  { parts.push(`${Math.floor(rem / 3600)}h`);  rem %= 3600; }
        if (rem >= 60)    { parts.push(`${Math.floor(rem / 60)}min`);  rem %= 60; }
        if (rem > 0 || parts.length === 0) parts.push(`${rem}s`);

        return parts.join(' ');
    }

    function format_time_of_day_preview(minutes: number): string {
        if (!isFinite(minutes) || isNaN(minutes)) return "?";

        let rounded = roundMinutes(minutes, questionRoundAnswerTime);
        
        rounded = ((rounded % 1440) + 1440) % 1440;

        const h = Math.floor(rounded / 60);
        const m = Math.floor(rounded % 60);

        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    }

    function eval_formula(formula: string, values: Record<string, string | number>): string {
        try {
            let expression = formula;
            Object.entries(values).forEach(([name, value]) => {
                const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

                expression = expression.replace(
                    new RegExp(`\\b${escaped}\\b`, 'g'),
                    String(value)
                );
            });
            return String(questionRoundAnswer ? Math.round(parseFloat(eval(expression).toFixed(10))) : parseFloat(eval(expression).toFixed(10)));
        } catch {
            return "?";
        }
    }

    function apply_format_spec(value: string | number, spec: string): string {
        const zeroPad = spec.match(/^0(\d+)d?$/);
        if (zeroPad) {
            return String(value).padStart(parseInt(zeroPad[1]), '0');
        }
        return String(value);
    }

    function render_preview(text: string, values: Record<string, string | number>): ReactNode[] {
        const parts: ReactNode[] = [];
        const variableRegex = /\{(\w+)(?::([^}]*))?\}/g;
        let lastIndex = 0;
        let keyIndex = 0;
        let match: RegExpExecArray | null;

        while ((match = variableRegex.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push(<span key={`text-${keyIndex++}`}>{text.slice(lastIndex, match.index)}</span>);
            }
            const name = match[1];
            const spec = match[2];
            const raw = values[name];
            const display = raw !== undefined
                ? (spec ? apply_format_spec(raw, spec) : raw)
                : `{${name}${spec ? ':' + spec : ''}}`;
            parts.push(
                <strong
                    key={`variable-${keyIndex++}`}
                    className="variable-highlight"
                >
                    {display}
                </strong>
            );
            lastIndex = variableRegex.lastIndex;
        }

        if (lastIndex < text.length) {
            parts.push(<span key={`text-${keyIndex++}`}>{text.slice(lastIndex)}</span>);
        }

        return parts;
    }

    function get_course_panel(){
        return courses == null || Object.keys(courses.courses).length == 0 || fullCourses == null ? (
            <h1>Fann inga kurser</h1>
        ) : (
        <>
        <div className="label-and-box">
            <label htmlFor="" style={{marginBottom:"-10px"}}>Aktiva Kurser</label>
        </div>
        <div className="course-grid" onWheel={(e) => {
            const el = e.currentTarget;

            if (el.scrollWidth <= el.clientWidth) return;

            e.preventDefault();

            const speed = 2; // adjust this
            el.scrollLeft -= e.deltaY * speed;
        }}>
            {(fullCourses).filter((c) => (c.active)).map((c) => (
                <label
                    key={c.course_code}
                    className={`card course-card ${selectedCourse === c.course_code ? "selected" : ""}`}
                >
                    <input
                    type="radio"
                    name="course"
                    value={c.course_code}
                    checked={selectedCourse === c.course_code}
                    onChange={() => setSelectedCourse(c.course_code)}
                    />
                    <div className="course-card-content">
                        <div className="course-info-control">
                            <span className="course-code">{c.course_code}</span>
                            <span className="course-name">{c.name}</span>
                            <span className="course-qcount">{get_course_question_count(c.course_code, courses)} frågor</span>
                        </div>
                        <div className="course-info-control">
                            <button className="table-button edit-button" onClick={(e) => {
                                e.stopPropagation();
                                openViewing(0, c.id.toString());
                            }} title="Redigera"

                            ><img src={edit} alt="Redigera" /></button>
                            <button className={`table-button ${c.active ? "archive-button" : "unarchive-button"}`} onClick={(e) => {
                                e.stopPropagation();
                                void handleArchive(0, c.id.toString(), c.active);
                            }} title = "Arkivera"
                            ><img src={c.active ? archivedown : archiveup} alt={c.active ? "Arkivera" : "Återställ"} /></button>
                        </div>
                    </div>
                </label>
                ))}
        </div>
        <div className="label-and-box" style={{marginBottom:"-10px"}}>
            <label htmlFor="">Arkiverade Kurser</label>
        </div>
        <div className="course-grid" onWheel={(e) => {
            const el = e.currentTarget;

            if (el.scrollWidth <= el.clientWidth) return;

            e.preventDefault();

            const speed = 2; // adjust this
            el.scrollLeft -= e.deltaY * speed;
        }}>
            {(fullCourses).filter((c) => (!c.active)).map((c) => (
                <label
                    key={c.course_code}
                    className={`card course-card ${selectedCourse === c.course_code ? "selected" : ""}`}
                >
                    <input
                    type="radio"
                    name="course"
                    value={c.course_code}
                    checked={selectedCourse === c.course_code}
                    onChange={() => setSelectedCourse(c.course_code)}
                    />
                    <div className="course-card-content">
                        <div className="course-info-control">
                            <span className="course-code">{c.course_code}</span>
                            <span className="course-name">{c.name}</span>
                            <span className="course-qcount">{get_course_question_count(c.course_code, courses)} frågor</span>
                        </div>
                        <div className="course-info-control">
                            <button className="table-button edit-button" onClick={(e) => {
                                e.stopPropagation();
                                openViewing(0, c.id.toString());
                            }} title="Redigera"

                            ><img src={edit} alt="Redigera" /></button>
                            <button className={`table-button ${c.active ? "archive-button" : "unarchive-button"}`} onClick={(e) => {
                                e.stopPropagation();
                                void handleArchive(0, c.id.toString(), c.active);
                            }} title = "Arkivera"
                            ><img src={c.active ? archivedown : archiveup} alt={c.active ? "Arkivera" : "Återställ"} /></button>
                        </div>
                    </div>
                </label>
                ))}
        </div>
        </>
        )
    }

    function get_category_panel(){
        return( categories == null || categories.length == 0 ? (
            <h1>Fann inga kategorier</h1>
        ) : (
            <div className="category-dropdowns">
                <table>
                    <thead className="category-table-main-header">
                        <tr>
                            <th>Namn</th>
                            <th>Kategorin innegår i dessa kurser</th>
                            <th>Aktiva frågor (Alla frågor)</th>
                            <th>Status</th>
                            <th>Åtgärder</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[...categories].filter((cat:Category) => seeArchive || cat.active).sort((a, b) => a.name.localeCompare(b.name)).map((cat:Category) =>(
                            <Fragment key={cat.id}>
                            <tr key={cat.id} className={`secondary-table-header ${cat.down ? "selected-header" : ""}`} onClick={()=>handle_category_expand(cat.id)}>
                                <td>{cat.name}</td>
                                <td>{cat.courses.map((c:Course) => (
                                    <span key={c.id} className="c-code-table">{c.course_code} </span>
                                ))}</td>
                                <td>
                                   {cat.questions.filter((q: Question) => q.active).length} ({cat.questions.length})
                                </td>
                                <td><span className={cat.active ? "status active" : "status archived"}>{cat.active ? "Aktiv" : "Arkiverad"}</span></td>
                                <td>
                                    <button className="table-button new-question-button" onClick={(e) => {
                                        e.stopPropagation();
                                        setCategoryToAddQuestionTo(cat);
                                        openViewing(6, null);
                                    }} title="Lägg till fråga"
                                    ><img src={add} alt="Lägg till fråga" /></button>
                                    <button className="table-button edit-button" onClick={(e) => {
                                        e.stopPropagation();
                                        openViewing(1, cat.id.toString());
                                    }} title="Redigera"
                                    ><img src={edit} alt="Redigera" /></button>
                                    <button className={`table-button ${cat.active ? "archive-button" : "unarchive-button"}`} onClick={(e) => {
                                        e.stopPropagation();
                                        void handleArchive(1, cat.id.toString(), cat.active);
                                    }} title="Arkivera"
                                    ><img src={cat.active ? archivedown : archiveup} alt={cat.active ? "Arkivera" : "Återställ"} /></button>
                                </td>
                            </tr>
                            {cat.down &&
                                <tr key={`expanded-${cat.id}`}>
                                    <td colSpan={5}>
                                        <table className="expanded-questions-table">
                                            <thead>
                                                <tr>
                                                    <th>ID</th>
                                                    <th>QID</th>
                                                    <th>Fråga</th>
                                                    <th>Status</th>
                                                    <th>Åtgärder</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {[...cat.questions].filter((q: Question) => seeArchive || q.active).sort((a, b) => a.question_number - b.question_number).map((q: Question) => (
                                                    <tr key={q.id}>
                                                        <td>{q.question_number}</td>
                                                        <td>{q.id}</td>
                                                        <td>{q.excerpt}</td>
                                                        <td><span className={q.active ? "status active" : "status archived"}>{q.active ? "Aktiv" : "Arkiverad"}</span></td>
                                                        <td className="table-buttons">
                                                            <button title="Duplicera" className="table-button duplicate-button" onClick={(e) => {
                                                                e.stopPropagation();
                                                                setdupq(q);
                                                                setdupcat(cat);
                                                                setShowDupPopup(true);
                                                            }}><img src={copy} alt="Duplicera" /></button>
                                                            <button className="table-button edit-button" onClick={(e) => {
                                                                e.stopPropagation();
                                                                setCategoryToAddQuestionTo(cat);
                                                                openViewing(2, q.id.toString());
                                                            }} title="Redigera"
                                                            ><img src={edit} alt="Redigera" /></button>
                                                            <button className={`table-button ${q.active ? "archive-button" : "unarchive-button"}`} onClick={(e) => {
                                                                e.stopPropagation();
                                                                void handleArchive(2, q.id.toString(), q.active);
                                                            }} title = "Arkivera"
                                                            ><img src={q.active ? archivedown : archiveup} alt={q.active ? "Arkivera" : "Återställ"} /></button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                            }
                            </Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        ))
    }

    function get_unit_panel(){
        return( units == null || units.length == 0 ? (
            <h1>Fann inga enheter</h1>
        ) : (
            <div className="category-dropdowns">
                <table>
                    <thead className="category-table-main-header">
                        <tr>
                            <th>Namn</th>
                            <th>Alias</th>
                            <th>Status</th>
                            <th>Åtgärder</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[...units].sort((a, b) => a.name.localeCompare(b.name)).map((unit: FullUnit) => (
                            <tr key={unit.id} className="secondary-table-header">
                                <td>{unit.name}</td>
                                <td>{unit.aliases.map((alias) => <span key={alias.id} className="c-code-table">{alias.alias} </span>)}</td>
                                <td><span className={unit.active ? "status active" : "status archived"}>{unit.active ? "Aktiv" : "Arkiverad"}</span></td>
                                <td>
                                    <button className="table-button edit-button" onClick={() => openViewing(3, unit.id.toString())}><img src={edit} alt="Redigera" /></button>
                                    <button className={`table-button ${unit.active ? "archive-button" : "unarchive-button"}`} onClick={() => void handleArchive(3, unit.id.toString(), unit.active)}><img src={unit.active ? archivedown : archiveup} alt={unit.active ? "Arkivera" : "Återställ"} /></button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        ))
    }
    const [statsSelectedCourse, setStatsSelectedCourse] = useState<string>("")
    const [statsSelectedCourseId, setStatsSelectedCourseID] = useState<number|undefined>(undefined)
    const [statsSelectedCategory, setStatsSelectedCategory] = useState<string>("")
    const [statsSelectedCategoryId, setStatsSelectedCategoryID] = useState<number|undefined>(undefined)
    const [startDate, setStartDate] = useState(new Date(new Date().setMonth(new Date().getMonth() - 3)));
    const [endDate, setEndDate] = useState(new Date());
    const [sortBy, setSortBy] = useState<QuestionSortBy>("accuracy")
    useEffect(() => {
        if (tab === 4) handle_new_stats();
    }, [tab]);

    useEffect(() => {
        if (tab === 4) handle_new_stats();
    }, [
        statsSelectedCourseId,
        statsSelectedCategoryId,
        startDate,
        endDate,
        sortBy]);
    function handle_new_stats(){
        const formatted_start = startDate.toISOString().split("T")[0];
        const formatted_end = endDate.toISOString().split("T")[0];
        const params:QuestionStatsQuery = {
            course_id: statsSelectedCourseId,
            category_id: statsSelectedCategoryId,
            from_date: formatted_start,
            to_date: formatted_end,
            sort_by: sortBy
        }
        get_admin_statistics(params)
    }
    
    function get_stats_panel(){

        return(adminStats == null ? (<LoadingSpinner/>):(
            <>
                <div className="stats-datepickers">
                    <div className="label-and-box">
                        <label htmlFor="">Start Datum</label>
                        <DatePicker selected={startDate} onChange={(date:Date | null) => {if(date != null)setStartDate(date)}}/>
                    </div>
                    <div className="label-and-box">
                        <label htmlFor="">Slut Datum</label>
                        <DatePicker selected={endDate} onChange={(date:Date | null) => {if(date != null)setEndDate(date)}}/>
                    </div>
                </div>
                <div className="stats-heading-spans">
                    <span>Sessioner: {adminStats.overview.total_sessions}</span>
                    <span>Frågor Besvarade: {adminStats.overview.total_questions_answered}</span>
                    <span>Korrekta svar: {adminStats.overview.total_correct}</span>
                </div>
                <h2 style={{width:"100%", textAlign:"center", marginTop:"20px",marginBottom:"-40px",color:"var(--text-primary)"}}>Sorterad efter</h2>
                <div className="stats-heading-spans">
                    <span className={`${statsSelectedCourse != "" ? "c-code-table" : ""}`}>{statsSelectedCourse != "" ? statsSelectedCourse : "Ingen kurs vald"} </span>
                    <span>{statsSelectedCategory != "" ? statsSelectedCategory : "Ingen kategori vald"}</span>
                </div>
                <div className="category-dropdowns">
                <div className="label-and-box"><label htmlFor="">Kurser</label></div>
                <table>
                    <thead className="category-table-main-header">
                        <tr>
                            <th>Namn</th>
                            <th>KursKod</th>
                            <th>Sessioner</th>
                            <th>Utförda Frågor</th>
                            <th>Rätt Svar</th>
                            <th>Rätt%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {adminStats.courses.courses.sort((a, b) => b.session_count - a.session_count).map((course) => (
                            <tr key={course.course_id} className={`secondary-table-header ${course.course_code === statsSelectedCourse ? "selected-header" : ""}`} onClick={()=>{statsSelectedCourse === course.course_code ? (setStatsSelectedCourse(""),setStatsSelectedCourseID(undefined)) : (setStatsSelectedCourse(course.course_code),setStatsSelectedCourseID(course.course_id))}}>
                                <td>{course.course_name}</td>
                                <td><span className="c-code-table">{course.course_code}</span></td>
                                <td>{course.session_count}</td>
                                <td>{course.questions_answered}</td>
                                <td>{course.correct_count}</td>
                                <td>
                                    <div className="stats-category-bar-group">
                                        <div className="stats-progress-bar">
                                            <div
                                                className="stats-progress-fill"
                                                style={{ width: `${course.accuracy_pct}%`, background: `${accColor(course.accuracy_pct != null ? course.accuracy_pct : 0)}` }}
                                            />
                                        </div>
                                        <span className="stats-mastery-pct">{Math.round(course.accuracy_pct != null ? course.accuracy_pct : 0)}%</span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="label-and-box"><label htmlFor="">Kategorier</label></div>
                <table>
                    <thead className="category-table-main-header">
                        <tr>
                            <th>Namn</th>
                            <th>Finns i kurserna</th>
                            <th>Sessioner</th>
                            <th>Utförda Frågor</th>
                            <th>Rätt Svar</th>
                            <th>Rätt%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {adminStats.categories.categories.sort((a, b) => b.session_count - a.session_count).map((cat) => (
                            <tr key={cat.category_id} className={`secondary-table-header ${cat.category_name === statsSelectedCategory ? "selected-header" : ""}`} onClick={()=>{statsSelectedCategory === cat.category_name ? (setStatsSelectedCategory(""),setStatsSelectedCategoryID(undefined)) : (setStatsSelectedCategory(cat.category_name),setStatsSelectedCategoryID(cat.category_id))}}>
                                <td>{cat.category_name}</td>
                                <td>{cat.linked_courses.map((c)=>(<span key={c.course_id} className="c-code-table">{c.course_code}</span>))}</td>
                                <td>{cat.session_count}</td>
                                <td>{cat.questions_answered}</td>
                                <td>{cat.correct_count}</td>
                                <td>
                                    <div className="stats-category-bar-group">
                                        <div className="stats-progress-bar">
                                            <div
                                                className="stats-progress-fill"
                                                style={{ width: `${cat.accuracy_pct}%`, background: `${accColor(cat.accuracy_pct != null ? cat.accuracy_pct : 0)}` }}
                                            />
                                        </div>
                                        <span className="stats-mastery-pct">{Math.round(cat.accuracy_pct != null ? cat.accuracy_pct : 0)}%</span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="stats-question-heading">
                    <div className="label-and-box"><label htmlFor="">Frågor</label></div>
                    <div className="label-and-box" style={{alignItems:"flex-end"}}>
                        <label htmlFor="">Sortera Frågor Efter:</label>
                        <div className="cp-tabs">
                            <Tab selected={sortBy == "accuracy"} text="Svårhetsgrad" on_Click={()=>setSortBy("accuracy")}></Tab>
                            <Tab selected={sortBy == "attempts"} text="Mängd Svar" on_Click={()=>setSortBy("attempts")}></Tab>
                        </div>
                    </div>
                </div>
                
                <table>
                    <thead className="category-table-main-header">
                        <tr>
                            <th>ID</th>
                            <th>Fråga</th>
                            <th>Mängd Svar</th>
                            <th>Rätt Svar</th>
                            <th>Svårhetsgrad</th>
                            <th>Rätt%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {adminStats.questions.questions.map((q) => (
                            <tr key={q.template_id} className="secondary-table-header">
                                <td>{q.template_id}</td>
                                <td>{q.template_text?.substring(0,60) + (q.template_text != null && q.template_text?.length > 50 ? "..." :"")}</td>
                                <td>{q.attempt_count}</td>
                                <td>{q.correct_count}</td>
                                <td><span className={`c-code-table ${q.difficulty}`}>{q.difficulty == "easy" ? "LÄTT" :(q.difficulty == "medium" ? "MEDIUM" : (q.difficulty == "hard" ? "SVÅR" : ""))}</span></td>
                                <td>
                                    <div className="stats-category-bar-group">
                                        <div className="stats-progress-bar">
                                            <div
                                                className="stats-progress-fill"
                                                style={{ width: `${q.accuracy_pct}%`, background: `${accColor(q.accuracy_pct != null ? q.accuracy_pct : 0)}` }}
                                            />
                                        </div>
                                        <span className="stats-mastery-pct">{Math.round(q.accuracy_pct != null ? q.accuracy_pct : 0)}%</span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            </>
        ))
    }

    return(
        <>
        {showduppopup && (
            <div className="overlay" onClick={() => setShowDupPopup(false)}>
                <div
                    className="delete-account-modal"
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="delete-account-header">
                        <h2>Duplicering är permanent!</h2>
                        <button className="table-button" onClick={() => setShowDupPopup(false)} aria-label="Avbryt">
                            <img src={exit} alt="Stäng" />
                        </button>
                    </div>
                    <p>Om du duplicerar en fråga kan du ej ta bort den, bara redigera/arkivera den. Är du säker att du vill duplicera denna fråga?</p>
                    <Button text="Duplicera" onClick={() => {setShowDupPopup(false),handleDuplicateQuestion(dupq, dupcat)}}></Button>
                </div>
            </div>
        )}
        {viewing && (
            <div className="overlay" onClick={(e) => {e.target == e.currentTarget ? closeViewing(): {}}}>
                <div className={`${viewingType === 0 || viewingType === 1 || viewingType == 4 || viewingType == 5 || viewingType == 3 || viewingType == 7 ? "viewing-popup-control-course-cat" : "viewing-popup-control"}`}>
                    {viewingType === null || !viewingData ? (
                        <LoadingSpinner />
                    ) : (
                        <>
                            {viewingType === 0 || viewingType === 4 ?
                                <div className="creation-preview">
                                    <div className="creation-viewing-header">
                                        <div className="creation-viewing-header-left">
                                            <h3>{viewingType === 0 ? "Redigera Kurs" : "Ny Kurs"}</h3>
                                        </div>
                                        <div className="creation-viewing-header-center">
                                            <Button text={viewingType === 0 ? "Spara" : "Lägg till"} onClick={viewingType === 0 ? handleEditCourse : handleSaveCourse} />
                                        </div>
                                        <div className="creation-viewing-header-right">
                                            <button onClick={()=>closeViewing()} className="table-button">
                                                {darkMode ? <img src={exit_dark} alt="Stäng" />: <img src={exit} alt="Stäng" />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="creation-viewing-body">
                                        <div className="label-and-box">
                                            <label htmlFor="cname">Kursnamn</label>
                                            <textarea name="coursename" id="cname" value={courseName} rows={1} onChange={(e) => {setCourseName(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`;}} spellCheck={false}></textarea>
                                        </div>
                                        <div className="label-and-box">
                                            <label htmlFor="ccode">Kurskod</label>
                                            <textarea name="coursecode" id="ccode" value={courseCode} rows={1} onChange={(e) => {setCourseCode(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`;}} spellCheck={false}></textarea>
                                        </div>
                                    </div>
                                </div>
                            : null}
                            {viewingType === 1 || viewingType === 5 ?
                                <div className="creation-preview">
                                    <div className="creation-viewing-header">
                                        <div className="creation-viewing-header-left">
                                            <h3>{viewingType === 1 ? "Redigera Kategori" : "Ny Kategori"}</h3>
                                        </div>
                                        <div className="creation-viewing-header-center">
                                            <Button text={viewingType === 1 ? "Spara" : "Lägg till"} onClick={viewingType === 1 ? handleEditCategory : handleSaveCategory} />
                                        </div>
                                        <div className="creation-viewing-header-right">
                                            <button onClick={() => closeViewing()} className="table-button">
                                                {darkMode ? <img src={exit_dark} alt="Stäng" /> : <img src={exit} alt="Stäng" />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="creation-viewing-body" style={{ flexDirection: "column"}}>
                                        <div className="label-and-box">
                                            <label htmlFor="catname">Kategorinamn</label>
                                            <textarea name="categoryname" id="catname" value={categoryName} rows={1} onChange={(e) => { setCategoryName(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`; }} spellCheck={false}></textarea>
                                        </div>
                                        <div className="label-and-box">
                                            <label>Välj kurser</label>
                                        </div>
                                        <div className="multiselect">
                                            <MultiSelect options={options} value={selectedCourses} onChange={setSelected} labelledBy="Filtrera kurser" 
                                            overrideStrings={{
                                                "allItemsAreSelected": "Alla kurser valda",
                                                "clearSearch": "Rensa sökning",
                                                "clearSelected": "Rensa valda kurser",
                                                "noOptions": "Inga kurser hittades...",
                                                "search": "Sök",
                                                "selectAll": "Välj alla kurser",
                                                "selectAllFiltered": "Välj alla (filtrerade)",
                                                "selectSomeItems": "Filtrera kurser...",
                                                "create": "Skapa"
                                            }}
                                            />
                                        </div>
                                        
                                        <div className="label-and-box">
                                            <label>Valda kurser</label>
                                            
                                            <div className="category-course-selection">
                                                <div className="category-course-chips">
                                                {selectedCourses.map((option) => (
                                                    <span key={option.value} className="c-code-table category-course-chip">
                                                    {option.label}

                                                    <button
                                                        className="chip-remove-btn"
                                                        onClick={() =>
                                                        setSelected((prev) =>
                                                            prev.filter((o) => o.value !== option.value)
                                                        )
                                                        }>×
                                                    </button>
                                                    </span>
                                                ))}
                                                </div>

                                                {/* <select className="category-course-select" value="" onChange={(e) => {
                                                    const id = parseInt(e.target.value);
                                                    if (!isNaN(id) && !selectedCourseIds.includes(id)) {
                                                        setSelectedCourseIds(prev => [...prev, id]);
                                                    }
                                                    e.target.value = "";
                                                }}>
                                                    <option value="">+ Lägg till kurs</option>
                                                    {fullCourses?.filter(c => c.active && !selectedCourseIds.includes(c.id)).map(c => (
                                                        <option key={c.id} value={c.id}>{c.course_code} – {c.name}</option>
                                                    ))}
                                                </select> */}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            : null}
                            {viewingType === 2 || viewingType === 6 ? 
                            <div className="creation-preview">
                                <div className="creation-viewing-header">
                                    <div className="creation-viewing-header-left">
                                        <h3>{viewingType === 2 ? "Redigera Fråga" : "Ny Fråga"}</h3>
                                        <div>
                                            <p>I kategorin</p>
                                            <span className="c-code-table">{categoryToAddQuestionTo?.name}</span>
                                        </div>
                                    </div>
                                    <div className="creation-viewing-header-center">
                                        <Button text={viewingType === 2 ? "Spara" : "Lägg till"} onClick={viewingType === 2 ? handleEditQuestion : handleSaveQuestion} />
                                    </div>
                                    <div className="creation-viewing-header-right">
                                        <button onClick={()=>closeViewing()} className="table-button">
                                            {darkMode ? <img src={exit_dark} alt="Stäng" />: <img src={exit} alt="Stäng" />}
                                        </button>
                                    </div>
                                </div>
                                <div className="creation-viewing-body" style={{overflow:"hidden"}}>
                                    <div className="creation-body-lhs">
                                        <label htmlFor="qtext">FRÅGETEXT</label>
                                        <textarea name="questiontext" id="qtext" value={questionText} onChange={(e) => setQuestionText(e.target.value)} spellCheck={false}></textarea>
                                        <hr />
                                        <div className="variables-section">
                                            <div className="preview-header">
                                                <label>VARIABLER ({variables.length})</label>
                                                <span className="variable-type-legend">
                                                    <span style={{color:"#e07b39"}}>Intervall</span>
                                                    <span style={{color:"#3dab6e"}}>Lista</span>
                                                    <span style={{color:"#7c5cbf"}}>Formel</span>
                                                    <span style={{color:"#3b7dd8"}}>Namn</span>
                                                </span>
                                            </div>
                                            <div className="variables-name">
                                                {variables.map((variable, index) => (
                                                    <span
                                                        key={index}
                                                        className={`c-code-table ${get_var_chip_class(variable.type)} variable-clickable`}
                                                        onClick={() => document.getElementById(`varname-${index}`)?.focus()}
                                                    >
                                                        * {variable.name}
                                                    </span>
                                                ))}
                                                <span
                                                    className="c-code-table variable-add-button"
                                                    onClick={() => {
                                                        const name = prompt("Variabelnamn:");
                                                        if (name && !variables.some((variable) => variable.name === name)) {
                                                            setVariables((prevVariables) => [
                                                                ...prevVariables,
                                                                {
                                                                    name,
                                                                    type: 0,
                                                                    min: null,
                                                                    max: null,
                                                                    decimals: null,
                                                                    step: null,
                                                                    arr: null,
                                                                    depends_on: null,
                                                                    formula: null,
                                                                    names: null,
                                                                },
                                                            ]);
                                                        }
                                                    }}
                                                >
                                                    + Ny variabel
                                                </span>
                                            </div>
                                            {variables.map((variable, index) => (
                                                <div key={index} className="variable-edit-section">
                                                    <input
                                                        id={`varname-${index}`}
                                                        className={`c-code-table ${get_var_chip_class(variable.type)} variable-input-chip`}
                                                        value={`* ${variable.name}`}
                                                        onChange={(e) => {
                                                            const newName = e.target.value.replace(/^\*\s*/, "").trim();
                                                            const oldName = variables[index].name;
                                                            setVariables((prevVariables) => {
                                                                const newVariables = [...prevVariables];
                                                                newVariables[index] = { ...newVariables[index], name: newName };
                                                                return newVariables;
                                                            });
                                                            setQuestionText((prevText) => prevText.replaceAll(`{${oldName}}`, `{${newName}}`));
                                                        }}
                                                    />
                                                    <div className="variable-types">
                                                        <Tab text="Interval" on_Click={() => {change_var_type(index, 0), setVariableTab(prev => { const newTabs = [...prev]; newTabs[index] = 0; return newTabs; })}} selected={variableTab[index] === 0}></Tab>
                                                        <Tab text="Lista" on_Click={() => {change_var_type(index, 1), setVariableTab(prev => { const newTabs = [...prev]; newTabs[index] = 1; return newTabs; })}} selected={variableTab[index] === 1}></Tab>
                                                        <Tab text="Formel" on_Click={() => {change_var_type(index, 2), setVariableTab(prev => { const newTabs = [...prev]; newTabs[index] = 2; return newTabs; })}} selected={variableTab[index] === 2}></Tab>
                                                        <Tab text="Namn" on_Click={() => {change_var_type(index, 3), setVariableTab(prev => { const newTabs = [...prev]; newTabs[index] = 3; return newTabs; })}} selected={variableTab[index] === 3}></Tab>
                                                    </div>
                                                    {variableTab[index] === 0 && (
                                                        <div className="variable-interval">
                                                            <div className="label-and-box">
                                                                <label htmlFor={`min-${index}`}>Min</label>
                                                                <input id={`min-${index}`} type="number" value={variable.min ?? ""} onChange={(e) => {
                                                                    const newMin = e.target.value === "" ? null : parseFloat(e.target.value);
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], min: newMin };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                            <div className="label-and-box">
                                                                <label htmlFor={`max-${index}`}>Max</label>
                                                                <input id={`max-${index}`} type="number" value={variable.max ?? ""} onChange={(e) => {
                                                                    const newMax = e.target.value === "" ? null : parseFloat(e.target.value);
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], max: newMax };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                            <div className="label-and-box">
                                                                <label htmlFor={`step-${index}`}>Step</label>
                                                                <input id={`step-${index}`} type="number" value={variable.step ?? ""} onChange={(e) => {
                                                                    const newStep = e.target.value === "" ? null : parseFloat(e.target.value);
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], step: newStep };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                            <div className="label-and-box">
                                                                <label htmlFor={`decimals-${index}`}>Decimals</label>
                                                                <input id={`decimals-${index}`} type="number" value={variable.decimals ?? ""} onChange={(e) => {
                                                                    const newDecimals = e.target.value === "" ? null : parseFloat(e.target.value);
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], decimals: newDecimals };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                        </div>
                                                    )}
                                                    {variableTab[index] === 1 && (
                                                        <div className="variable-lista">
                                                            <div className="label-and-box">
                                                                <label htmlFor={`list-${index}`}>Värden (komma-separerade)</label>
                                                                <input id={`list-${index}`} type="text" value={variable.arr ? variable.arr.join(",") : ""} onChange={(e) => {
                                                                    const newArr = e.target.value.split(",").map((value) => value.trim());
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], arr: newArr };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                        </div>
                                                    )}
                                                    {variableTab[index] === 2 && (
                                                        <div className="variable-funktion">
                                                            <div className="label-and-box">
                                                                <label htmlFor={`depends-on-${index}`}>Beror på (variabler)</label>
                                                                <input id={`depends-on-${index}`} type="text" value={variable.depends_on ? variable.depends_on.join(",") : ""} onChange={(e) => {
                                                                    const newDependsOn = e.target.value.split(",").map((value) => value.trim()).filter(Boolean);
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], depends_on: newDependsOn };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                            <div className="label-and-box">
                                                                <label htmlFor={`formula-${index}`}>Formel</label>
                                                                <input id={`formula-${index}`} type="text" value={variable.formula || ""} onChange={(e) => {
                                                                    const newFormula = e.target.value;
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], formula: newFormula };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                            </div>
                                                        </div>
                                                    )}
                                                    {variableTab[index] === 3 && (
                                                        <div className="variable-name">
                                                            <div className="label-and-box">
                                                                <label htmlFor={`standard-names-${index}`}>Använd standardnamn</label>
                                                                <input id={`standard-names-${index}`} type="checkbox" checked={typeof variable.names === "string"} onChange={(e) => {
                                                                    const checked = e.target.checked;
                                                                    setVariables(prev => {
                                                                        const newVars = [...prev];
                                                                        newVars[index] = { ...newVars[index], names: checked ? "$STANDARD_NAMES" : [] };
                                                                        return newVars;
                                                                    });
                                                                }} />
                                                                {typeof variable.names !== "string" && (
                                                                    <div className="label-and-box">
                                                                        <label htmlFor={`variable-names-${index}`}>Använd anpassade namn</label>
                                                                        <input id={`variable-names-${index}`}
                                                                            type="text"
                                                                            defaultValue={Array.isArray(variable.names) ? variable.names.join(", ") : ""}
                                                                            onBlur={(e) => {
                                                                                const value = e.target.value;

                                                                                setVariables(prev => {
                                                                                    const newVars = [...prev];

                                                                                    newVars[index] = {
                                                                                        ...newVars[index],
                                                                                        names: value
                                                                                            .split(",")
                                                                                            .map(name => name.trim())
                                                                                            .filter(Boolean)
                                                                                    };

                                                                                    return newVars;
                                                                                });
                                                                            }}
                                                                        />
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                        <hr />
                                        <div className="variable-edit-section">
                                            <span className="c-code-table">Beräkning av rätt svar</span>
                                            <div className="label-and-box">
                                                <label htmlFor="answer-type">Svarstyp</label>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                                    <select id="answer-type" value={questionAnswerType} onChange={(e) => {
                                                        const t = e.target.value;
                                                        setQuestionAnswerType(t);
                                                        if (t === "time_of_day") setQuestionUnit("kl");
                                                        else if (t === "duration") setQuestionUnit("");
                                                    }}>
                                                        <option value="numeric">Numeriskt</option>
                                                        <option value="time_of_day">Klockslag</option>
                                                        <option value="duration">Tidslängd</option>
                                                    </select>
                                                </div>
                                            </div>
                                            {questionAnswerType === "numeric" && (
                                                <div className="label-and-box">
                                                    <label htmlFor="rounding">
                                                        Avrunda svar till heltal
                                                    </label>
                                                    <input
                                                        id="rounding"
                                                        type="checkbox" 
                                                        checked={questionRoundAnswer} 
                                                        onChange={(e) => setQuestionRoundAnswer(e.target.checked)} 
                                                        style={{ width: 'auto', marginBottom: 0 }}
                                                    />
                                                </div>
                                                        
                                            )}
                                            {(questionAnswerType === "time_of_day" || questionAnswerType === "duration") && (
                                                <div className="label-and-box">
                                                    <label>
                                                        Avrunda till
                                                    </label>
                                                    <div className="round-radio">
                                                        <div className="label-and-box">
                                                            <label htmlFor="dagar">
                                                                Dagar
                                                            </label>
                                                            <input
                                                                id="dagar"
                                                                type="radio" 
                                                                checked={questionRoundAnswerTime === "d"} 
                                                                onChange={(e) => setQuestionRoundAnswerTime(e.target.checked ? "d" : "")} 
                                                                style={{ width: 'auto', marginBottom: 0 }}
                                                            />
                                                        </div>
                                                        <div className="label-and-box">
                                                            <label htmlFor="timmar">
                                                                Timmar
                                                            </label>
                                                            <input
                                                                id="timmar"
                                                                type="radio" 
                                                                checked={questionRoundAnswerTime === "h"} 
                                                                onChange={(e) => setQuestionRoundAnswerTime(e.target.checked ? "h" : "")} 
                                                                style={{ width: 'auto', marginBottom: 0 }}
                                                            />
                                                        </div>
                                                        <div className="label-and-box">
                                                            <label htmlFor="minuter">
                                                                Minuter
                                                            </label>
                                                            <input
                                                                id="minuter"
                                                                type="radio" 
                                                                checked={questionRoundAnswerTime === "min"} 
                                                                onChange={(e) => setQuestionRoundAnswerTime(e.target.checked ? "min" : "")} 
                                                                style={{ width: 'auto', marginBottom: 0 }}
                                                            />
                                                        </div>
                                                        <div className="label-and-box">
                                                            <label htmlFor="sekunder">
                                                                Sekunder
                                                            </label>
                                                            <input
                                                                id="sekunder"
                                                                type="radio" 
                                                                checked={questionRoundAnswerTime === "s"} 
                                                                onChange={(e) => setQuestionRoundAnswerTime(e.target.checked ? "s" : "")} 
                                                                style={{ width: 'auto', marginBottom: 0 }}
                                                            />
                                                        </div>

                                                    </div>
                                                    
                                                </div>
                                            )}
                                                
                                            
                                            <div className="variable-interval" style={{ gap: '1rem' }}>
                                                <div className="label-and-box" style={{ flex: 1 }}>
                                                    <label htmlFor="answer-min">Minsta acceptabla värde</label>
                                                    <input id="answer-min" type="number" step="any" value={questionAnswerMin} onChange={(e) => setQuestionAnswerMin(e.target.value)} />
                                                </div>
                                                <div className="label-and-box" style={{ flex: 1 }}>
                                                    <label htmlFor="answer-max">Högsta acceptabla värde</label>
                                                    <input id="answer-max" type="number" step="any" value={questionAnswerMax} onChange={(e) => setQuestionAnswerMax(e.target.value)} />
                                                </div>
                                            </div>
                                            <div className="label-and-box">
                                                <label htmlFor="answer-formula">
                                                    Svarsformel{questionAnswerType === "duration" ? " (returnerar sekunder)" : questionAnswerType === "time_of_day" ? " (returnerar min från midnatt)" : ""}
                                                </label>
                                                <input id="answer-formula" type="text" value={questionFormula} onChange={(e) => setQuestionFormula(e.target.value)} />
                                            </div>
                                            <div className="variable-interval">
                                                {questionAnswerType !== "duration" && (
                                                    <div className="label-and-box">
                                                        <label htmlFor="unit">Enhet</label>
                                                        <select name="unit" id="unit" value={questionUnit} onChange={(e) => setQuestionUnit(e.target.value)} disabled={questionAnswerType === "time_of_day"}>
                                                            <option value={""}>Ingen Enhet</option>
                                                            {units?.map((unit)=>(
                                                                <option value={unit.name}>{unit.name}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                )}
                                                <div className="label-and-box">
                                                    <label htmlFor="tolerance">
                                                        {questionAnswerType === "duration" ? "Tolerans (sek)" : questionAnswerType === "time_of_day" ? "Tolerans (min)" : "Tolerans"}
                                                    </label>
                                                    <input id="tolerance" type="text" value={questionTolerance} onChange={(e) => setQuestionTolerance(e.target.value)} />
                                                </div>
                                            </div>
                                        </div>
                                        <hr />
                                        <div className="variable-edit-section">
                                            <div className="question-hints-header">
                                                <span className="c-code-table">Ledtrådar</span>
                                                <button className="table-button add-hint-button" onClick={() => setQuestionHints((prevHints) => [...prevHints, ""])}><img src={add} alt="Lägg till ledtråd" /></button>
                                            </div>
                                            {questionHints.map((hint, index) => (
                                                <div key={index} className="label-and-box">
                                                    <label htmlFor={`hint-${index}`}>Ledtråd {index + 1}</label>
                                                    <div className="hint-and-delete">
                                                        <input id={`hint-${index}`} type="text" value={hint} onChange={(e) => {
                                                            const newHint = e.target.value;
                                                            setQuestionHints((prevHints) => {
                                                                const newHints = [...prevHints];
                                                                newHints[index] = newHint;
                                                                return newHints;
                                                            });
                                                        }}/>
                                                        <button className="table-button" onClick={() => {
                                                            setQuestionHints((prevHints) => prevHints.filter((_, hintIndex) => hintIndex !== index));
                                                        }}>{darkMode ? <img src={exit_dark} alt="Ta bort ledtråd" /> : <img src={exit} alt="Ta bort ledtråd" />}</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <hr />
                                        <div className="variable-edit-section">
                                            <span className="c-code-table">Hjälpplänk</span>
                                            <div className="label-and-box">
                                                <label htmlFor="question-link">URL</label>
                                                <input id="question-link" type="text" value={questionLink} placeholder="tex: https://fass.se" onChange={(e) => setQuestionLink(e.target.value)} />
                                            </div>
                                        </div>
                                    </div>
                                    <div className="creation-body-rhs">
                                        <div className="variable-edit-section">
                                            <div className="preview-header">
                                                <label className="c-code-table">FÖRHANDSGRANSKNING</label>
                                                <button className="table-button refresh-preview-button" onClick={() => setSampledValues(sample_variables())}>
                                                    <img src={refresh} alt="Slumpa nya värden" />
                                                </button>
                                            </div>
                                            <div className="preview-text">
                                                {render_preview(questionText, sampledValues)}
                                            </div>
                                        </div>
                                        {questionFormula && (() => {
                                            const sampledAnswerStr = eval_formula(questionFormula, sampledValues);
                                            const sampledAnswerValue = parseFloat(sampledAnswerStr);
                                            const minVal = questionAnswerMin !== "" ? parseFloat(questionAnswerMin) : -Infinity;
                                            const maxVal = questionAnswerMax !== "" ? parseFloat(questionAnswerMax) : Infinity;
                                            const isOutOfBounds = isFinite(sampledAnswerValue) && (sampledAnswerValue < minVal || sampledAnswerValue > maxVal);

                                            return (
                                                <div className="variable-edit-section answer-section">
                                                    <div className="answer-labels">
                                                        <label className="c-code-table">RÄTT SVAR</label>
                                                        <label className="c-code-table">TOLERANS</label>
                                                    </div>
                                                    <div className="answer-values">
                                                        <span>
                                                            <strong className={`answer-value ${isOutOfBounds ? 'out-of-bounds' : ''}`} style={isOutOfBounds ? { color: '#ffb347' } : {}}>
                                                                {questionAnswerType === "duration"
                                                                    ? format_duration_preview(parseFloat(sampledAnswerStr))
                                                                    : questionAnswerType === "time_of_day"
                                                                    ? format_time_of_day_preview(parseFloat(sampledAnswerStr))
                                                                    : sampledAnswerStr
                                                                }
                                                            </strong>
                                                            {questionAnswerType === "numeric" && <span className="answer-unit" style={isOutOfBounds ? { color: '#ffb347' } : {}}>{questionUnit}</span>}
                                                        </span>
                                                        <strong className="answer-tolerance">± {questionTolerance || 0}{questionAnswerType === "duration" ? "s" : questionAnswerType === "time_of_day" ? "min" : ""}</strong>
                                                    </div>
                                                    <code className="answer-formula-code">{questionFormula} = {sampledAnswerStr}{questionAnswerType !== "numeric" ? " (råvärde)" : ""}</code>
                                                    
                                                    {isOutOfBounds && (
                                                        <div className="answer-warning" style={{ marginTop: '1rem', color: '#ffb347', fontSize: '0.9rem', backgroundColor: 'rgba(255, 179, 71, 0.1)', padding: '0.75rem', borderRadius: '12px' }}>
                                                            <strong>Varning:</strong> Det genererade svaret ({sampledAnswerStr}) ligger utanför de tillåtna gränserna ({questionAnswerMin !== "" ? questionAnswerMin : "-∞"} till {questionAnswerMax !== "" ? questionAnswerMax : "∞"}). 
                                                            Eleven kan få frågor med svar som inte utvärderas rimligt, eller så kan backend ta för lång tid att generera fram rätt variabler.
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })()}
                                    </div>
                                </div>
                            </div>
                            :null}
                            {viewingType === 3 || viewingType === 7 ? 
                                <div className="creation-preview">
                                    <div className="creation-viewing-header">
                                        <div className="creation-viewing-header-left">
                                            <h3>{viewingType === 3 ? "Redigera Enhet" : "Ny Enhet"}</h3>
                                        </div>
                                        <div className="creation-viewing-header-center">
                                            <Button text={viewingType === 3 ? "Spara" : "Lägg till"} onClick={viewingType === 3 ? handleEditUnit : handleSaveUnit} />
                                        </div>
                                        <div className="creation-viewing-header-right">
                                            <button onClick={()=>closeViewing()} className="table-button">
                                                {darkMode ? <img src={exit_dark} alt="Stäng" />: <img src={exit} alt="Stäng" />}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="creation-viewing-body" style={{flexDirection:"column"}}>
                                        
                                        <div className="label-and-box">
                                            <label htmlFor="uname">Enhetens Bas Namn</label>
                                            <textarea name="coursename" id="uname" value={unitName} rows={1} onChange={(e) => {setUnitName(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`;}} spellCheck={false}></textarea>
                                        </div>
                                    
                                        <div className="variable-edit-section unit-edit-section">
                                            <div className="question-hints-header">
                                                <span className="c-code-table">Aliaser</span>
                                                <button className="table-button add-hint-button" onClick={() =>setUnitAliases(prev => [...prev,{id: -Date.now(), alias: "",},])}><img src={add} alt="Lägg till alias" /></button>
                                            </div>
                                            {unitAliases.map((alias, index) => (
                                                <div key={index} className="label-and-box">
                                                    <label htmlFor={`alias-${index}`}>Alias {index + 1}</label>
                                                    <div className="hint-and-delete">
                                                        <input id={`alias-${index}`} type="text" value={alias.alias} onChange={(e) => {
                                                            const newAlias = e.target.value;
                                                            setUnitAliases((prevAliases) => {
                                                                const newAliases = [...prevAliases];
                                                                newAliases[index].alias = newAlias;
                                                                return newAliases;
                                                            });
                                                        }}/>
                                                        <button className="table-button" onClick={() => {
                                                            const aliasToRemove = unitAliases[index];
                                                            if (aliasToRemove.id > 0) {
                                                                setDeletedUnitAliasIds(prev => [
                                                                    ...prev,
                                                                    aliasToRemove.id
                                                                ]);
                                                            }
                                                            setUnitAliases(prevAliases =>
                                                                prevAliases.filter((_, aliasIndex) =>
                                                                    aliasIndex !== index
                                                                )
                                                            );
                                                        }}>{darkMode ? <img src={exit_dark} alt="Ta bort alias" /> : <img src={exit} alt="Ta bort alias" />}</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            
                            : null}
                        </>
                    )}
                </div>
            </div>
        )}
            <div className="maindiv-control">
                {isLoading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="main-controlpanel">
                        {get_stats()}
                        <div className="changing-panel">
                            <div className="changing-panel-header">
                                <div className="cp-tabs">
                                    <Tab text="Kurser" selected={tab == 0} on_Click={()=>setTab(0)} expand="horizontal"></Tab>
                                    <Tab text="Kategorier / Frågor" selected={tab == 1} on_Click={()=>setTab(1)} expand="horizontal"></Tab>
                                    <Tab text="Enheter" selected={tab == 2} on_Click={()=>setTab(2)} expand="horizontal"></Tab>
                                    <Tab text="Statistik" selected={tab == 4} on_Click={()=>setTab(4)} expand="horizontal"></Tab>
                                    {canManageUserRoles && <Tab text="Admin" selected={tab == 3} on_Click={()=>setTab(3)} expand="horizontal"></Tab>}
                                    <button className="table-button" onClick={()=>window.open("https://docs.google.com/document/d/1kmEtF0oWLtwOKvBeoap4gHHz--CZ-GDpfwH_gMgObbc", "_blank")}><img src={darkMode ? question_dark : question} alt="question" /> </button>
                                </div>
                                <div className="add-new-button">
                                    {tab == 0 && <Button text={width < 700 ? "Ny kurs" : "Lägg till ny kurs"} onClick={()=>{openViewing(4, null)}}></Button>}
                                    {tab == 1 && <Button text={width < 700 ? "Ny kategori" : "Lägg till ny kategori"} onClick={() => openViewing(5, null)}></Button>}
                                    {tab == 2 && <Button text={width < 700 ? "Ny enhet" : "Lägg till ny enhet"} onClick={() => {openViewing(7, null)}}></Button>}
                                </div>
                            </div>
                            {(tab == 1 || tab == 2) && 
                            <div className="label-and-box">
                                <label htmlFor="see-archive">Visa arkiverat innehåll</label>
                                <input type="checkbox"  id="see-archive" checked={seeArchive} onChange={(e) => setSeeArchive(e.target.checked)} style={{ width: 'auto', marginBottom: 0 }}/>
                            </div>}
                            {tab == 0 && get_course_panel()}
                            {tab == 1 && get_category_panel()}
                            {tab == 2 && get_unit_panel()}
                            {tab == 4 && get_stats_panel()}
                            {tab == 3 && canManageUserRoles && get_admin_users()}
                        </div>
                    </div>
                )}
            </div>
            {deleteUserConfirm ? (
                <div
                    className="overlay"
                    onClick={() => {
                        if(deletingUserId === null){
                            setDeleteUserConfirm(null);
                        }
                    }}
                >
                    <div
                        className="admin-delete-user-modal"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="delete-account-header">
                            <h2>Avaktivera konto?</h2>
                            <button className="table-button" onClick={() => setDeleteUserConfirm(null)} disabled={deletingUserId !== null} aria-label="Stäng avaktivera konto dialog">
                                <img src={exit} alt="Stäng" />
                            </button>
                        </div>
                        <p>
                            {deleteUserDescriptionStart}{" "}
                            <strong>{deleteUserConfirm.email}</strong>{" "}
                            {deleteUserDescriptionEnd}
                        </p>
                        {deleteUserError ? (
                            <p className="admin-delete-user-error">{deleteUserError}</p>
                        ) : null}
                        <div className="admin-delete-user-actions">
                            <div className="button-wrapper">
                                <Button
                                    img={[deleteaccount, "Avaktivera konto"]}
                                    onClick={() => void deactivate_admin_user(deleteUserConfirm)}
                                    disabled={deletingUserId !== null}
                                    text={deletingUserId !== null ? "Avaktiverar..." : "Avaktivera konto"}
                                    color="#db6767"
                                    hover="#db6767"
                                ></Button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}
            <Footer></Footer>
        </>
    )
}
