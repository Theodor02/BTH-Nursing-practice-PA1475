import "./history.css"
import Button from "../components/Button";
import ResultOverlay from "../components/ResultOverlay"
import LoadingSpinner from "../components/LoadingSpinner";
import { useNavigate, type NavigateFunction } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { useScreenWidth } from "../services/screenwidth";
import Tab from "../components/tab"
import { apiFetch } from "../services/apt";

//https://www.svgrepo.com/svg/529592/flame
import flame from "../assets/flame.svg"

const json_temp = '{"previous_answers":[ {"id":"108402","date":"2012-04-23 18:25:43", "course":"DV0000", "categories":["Spädning", "dosberäkning"], "correct":"10", "total":"50"}, {"id":"108403", "date":"2013-06-13 08:23:33", "course":"DV0000", "categories":["Spädning", "dosberäkning"], "correct":"10", "total":"50"}]}'
interface Root {
    user_id: number;
    sessions: Session[];
}

export interface Session {
    id: number;
    user_id: number;
    course_id: number;
    category_id: number;
    created_at: string;
    course_code: string;
    category_name: string;
    category_names: string[];
    score: string;
    questions: SessionQuestions;
}

interface SessionQuestions {
    attempt_id: string;
    questions: Record<string, QuestionItem>;
    summary: Summary;
}

interface QuestionItem {
    id: string;
    template_id: string;
    question: string;
    correct_answer: string | number;
    user_answer: string;
    unit: string;
    tolerance: number;
    is_correct: boolean;
    is_scored: boolean;
    variables: Record<string, number>;
}

interface Summary {
    answered_count: number;
    correct_count: number;
    scored_count: number;
    score: number;
}

// stats

interface Period {
  from: string | null;
  to: string | null;
}

interface UserCategoryPerformance {
  category_id: number;
  name: string;
  accuracy_pct: number;
}

interface UserStatsOverviewResponse {
  period: Period;
  user_id: number;
  total_sessions: number;
  total_questions: number;
  overall_accuracy_pct: number | null;
  current_streak: number;
  longest_streak: number;
  best_category: UserCategoryPerformance | null;
  worst_category: UserCategoryPerformance | null;
  estimated_practice_minutes: number;
}

interface UserMasteryCategory {
  category_id: number;
  category_name: string;
  session_count: number;
  mastery_pct: number;
  last_practiced: string;
}

interface UserMasteryCourse {
  course_id: number;
  course_code: string;
  course_name: string;
  session_count: number;
  mastery_pct: number;
  categories: UserMasteryCategory[];
}

interface UserMasteryStatsResponse {
  period: Period;
  user_id: number;
  courses: UserMasteryCourse[];
}

interface UserActivityDay {
  date: string;
  session_count: number;
}

interface UserActivityStatsResponse {
  user_id: number;
  weeks: number;
  days: UserActivityDay[];
}

interface Statistics {
    general: UserStatsOverviewResponse;
    mastery: UserMasteryStatsResponse;
    activity: UserActivityStatsResponse
}

interface AggregatedCategoryStats {
    category_id: number;
    category_name: string;

    total_sessions: number;

    mastery_pct: number;

    last_practiced: string;
}

interface CategoryLists {
    best: AggregatedCategoryStats[];
    worst: AggregatedCategoryStats[];
}

function getBestAndWorstCategories(courses: UserMasteryCourse[], limit: number = 5): CategoryLists {

    const categoryMap = new Map<number, {
        category_id: number;
        category_name: string;

        total_sessions: number;
        weighted_mastery_sum: number;

        last_practiced: string;
    }>();

    for (const course of courses) {

        for (const category of course.categories) {

            const existing = categoryMap.get(category.category_id);

            if (!existing) {

                categoryMap.set(category.category_id, {
                    category_id: category.category_id,
                    category_name: category.category_name,

                    total_sessions: category.session_count,

                    weighted_mastery_sum:
                        category.mastery_pct * category.session_count,

                    last_practiced: category.last_practiced
                });

            } else {

                existing.total_sessions += category.session_count;

                existing.weighted_mastery_sum +=
                    category.mastery_pct * category.session_count;
                if (
                    new Date(category.last_practiced) >
                    new Date(existing.last_practiced)
                ) {
                    existing.last_practiced = category.last_practiced;
                }
            }
        }
    }

    const aggregated: AggregatedCategoryStats[] =
        Array.from(categoryMap.values()).map((cat) => ({
            category_id: cat.category_id,
            category_name: cat.category_name,

            total_sessions: cat.total_sessions,

            mastery_pct: Math.round((cat.weighted_mastery_sum / cat.total_sessions) * 10) / 10,
            last_practiced: cat.last_practiced
        }));

    const sorted = aggregated.sort(
        (a, b) => b.mastery_pct - a.mastery_pct
    );

    return {
        best: sorted.slice(0, limit),

        worst: [...sorted]
            .reverse()
            .slice(0, limit)
    };
}

async function getSessions(): Promise<Root> {
    const res = await apiFetch("/api/sessions");
    return await res.json();
}

async function get_stats(days: number): Promise<Statistics> {
    const url1 = days ? `/api/stats/overview?days=${days}` : `/api/stats/overview`
    const url2 = days ?  `/api/stats/activity?weeks=${days/7}` : `/api/stats/activity`
    const url3 = days ? `/api/stats/mastery?days=${days}` : `/api/stats/mastery`
    const [overviewRes, activityRes, masteryRes] = await Promise.all([
        apiFetch(url1),
        apiFetch(url2),
        apiFetch(url3),
    ]);

    if (!overviewRes.ok || !activityRes.ok || !masteryRes.ok) {
        throw new Error("Failed to fetch stats");
    }

    const overview =
        await overviewRes.json() as UserStatsOverviewResponse;

    const activity =
        await activityRes.json() as UserActivityStatsResponse;

    const mastery =
        await masteryRes.json() as UserMasteryStatsResponse;

    return {
        general: overview,
        activity,
        mastery,
    };
}

export function accColor(pct: number): string {
    if (pct >= 70) return "rgba(0, 197, 43, 0.85)";
    if (pct >= 50) return "#f2c94c";
    return "#FF5757";
}
function heatmapColor(count: number): string {
    if (count === 0) return "var(--heatmap-empty)";
    if (count === 1) return "var(--heatmap-light)";
    if (count === 2) return "var(--heatmap-medium)";
    return "var(--heatmap-dark)";
}

export default function index(){
    const navigate = useNavigate()
    const [data, setData] = useState<Root | null>(null);
    const [stats, setStats] = useState<Statistics | null>(null);
    const [viewing, setViewing] = useState<Session | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [statLength, setStatLength] = useState<number>(0);
    const [selectedCourse, setSelectedCourse] = useState<string>("");
    const [tab, setTab] = useState<number>(0)
    const width = useScreenWidth();
    const selectedCourseData = stats?.mastery.courses.find(
        (course) => course.course_code === selectedCourse
    );
    const categoryStats = stats == null ? null : getBestAndWorstCategories(
        stats?.mastery.courses
    );


    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            const result = await getSessions();
            console.log(result)
            setData(result);
            const stats = await get_stats(statLength);
            console.log(stats)
            setStats(stats);
            setSelectedCourse(
                Object.values(stats.mastery.courses).sort((a, b) => b.session_count - a.session_count)[0]?.course_code
            );
            setIsLoading(false);
        }
        fetchData();
    }, []);

    useEffect(() => {
        console.log(selectedCourse);
        console.log(categoryStats)
    },[selectedCourse])

    async function update_stats(days: number){
        setStatLength(days);
        const stats = await get_stats(days);
        console.log(stats)
        setStats(stats);
        setSelectedCourse(
            Object.values(stats.mastery.courses).sort((a, b) => b.session_count - a.session_count)[0]?.course_code
        );
    }

    function get_stats_page(){
        if(stats == null) return;
        const streak = stats.general.current_streak;
        const longest_streak = stats.general.longest_streak;
        const best_category = {name: stats.general.best_category?.name == null ? "" : stats.general.best_category?.name.substring(0,18) + (stats.general.best_category?.name.length > 18 ? "..." : ""), acc: stats.general.best_category?.accuracy_pct};
        const overall_acc = stats.general.overall_accuracy_pct;
        const total_questions =  stats.general.total_questions;
        const total_sessions =  stats.general.total_sessions;
        const est_time = stats.general.estimated_practice_minutes

        return(
            <div className="general-stats-history">
                <div className="stat-panel-frame">
                    <div className="stat-panel-history">
                        <span>Streak</span>
                        <p className={`${streak > 1 ? "streak-text" : ""}`}>{streak} Dagar {streak > 1 ? <img src={flame} alt="Flamma"></img>: <></>}</p>
                        <span>Längsta: {longest_streak} Dagar</span>
                    </div>
                </div>
                <div className="stat-panel-frame">
                    <div className="stat-panel-history">
                        <span>Försök</span>
                        <p>{total_sessions} st</p>
                        <span>Estimerad Tid~: {(est_time - est_time%60)/60}:{est_time%60}</span>
                        
                    </div>
                </div>
                <div className="stat-panel-frame">
                    <div className="stat-panel-history">
                        <span>Träffsäkerhet</span>
                        <p>{overall_acc}%</p>
                        <span>Frågor: {total_questions} st</span>
                    </div>
                </div>
            </div>
        )
    }

    function ActivityHeatmap() {
        if(stats == null ||stats.activity == null) return;
        const days = stats.activity.days;
        if (days.length === 0) return null;
    
        // Pad leading empty cells so the first cell lands on Monday (day index 1, Sunday=0)
        const firstDate = new Date(days[0].date);
        // getDay(): 0=Sun,1=Mon...6=Sat → Monday-based offset
        const rawDay = firstDate.getDay();
        const leadingPad = rawDay === 0 ? 6 : rawDay - 1; // Mon=0, Tue=1, ..., Sun=6
    
        const dayLabels = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"];
    
        return (
            <section className="stats-section">
                <h2 className="stats-section-title">Aktivitet</h2>
                <div className="stats-heatmap-wrapper">
                    <div className="stats-heatmap-days-label">
                        {dayLabels.map(d => <span key={d}>{d}</span>)}
                    </div>
                    <div className="stats-heatmap">
                        {Array.from({ length: leadingPad }).map((_, i) => (
                            <div
                                key={`pad-${i}`}
                                className="stats-heatmap-cell"
                                style={{ background: "transparent" }}
                            />
                        ))}
                        {days.map(day => (
                            <div
                                key={day.date}
                                className="stats-heatmap-cell"
                                style={{ background: heatmapColor(day.session_count) }}
                                title={`${day.date}: ${day.session_count} session${day.session_count !== 1 ? "er" : ""}`}
                            />
                        ))}
                    </div>
                </div>
            </section>
        );
    }
    
    


    function make_table() {
        if (!data) return null;

        return [...data.sessions].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).map((session, index) => (
            <tr key={index} onClick={() => {setViewing(session);}}>
                <td>{new Date(session.created_at).toLocaleString()}</td>
                <td><span className="c-code-table">{session.course_code}</span></td>
                <td>{(session.category_names?.length ? session.category_names : [session.category_name]).join(", ")}</td>
                <td>
                    {session.questions.summary.correct_count}/
                    {session.questions.summary.answered_count}
                </td>
            </tr>
        ));
    }
    return(
        <>
            {viewing ? (<ResultOverlay unique_session={viewing} onClose={() => setViewing(null)}></ResultOverlay>):
            
            <main>
                <div className="maindiv-history">
                    
                    <div className="prevquestiontablehousing">
                        {get_stats_page()}
                        <div className="prevquestiontablehousing-main">
                            <div className="cp-tabs">
                                <Tab text="Föregående Försök" selected={tab == 0} on_Click={()=>setTab(0)} expand="horizontal"></Tab>
                                <Tab text="Statistik" selected={tab == 1} on_Click={()=>setTab(1)} expand="horizontal"></Tab>
                            </div>
                            {tab == 0 && 
                            <div className="table-scroll-wrapper"> 
                                <table>
                                    <thead>
                                    <tr>
                                        <th>Datum</th>
                                        <th>Kurskod</th>
                                        <th>Kategorier</th>
                                        <th>Poäng</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                        {isLoading ? (
                                            <tr>
                                                <td colSpan={4} style={{textAlign: 'center', verticalAlign: 'middle'}}>
                                                    <LoadingSpinner />
                                                </td>
                                            </tr>
                                        ) : (
                                            make_table()
                                        )}
                                    </tbody>
                                </table>
                            </div>}
                            {tab != 0 && <>
                            <div className="stats-time-period">
                                <Tab text="7d" selected={statLength === 7} on_Click={() => update_stats(7)}></Tab>
                                <Tab text="1M" selected={statLength === 28} on_Click={() => update_stats(28)}></Tab>
                                <Tab text="All" selected={statLength === 0} on_Click={() => update_stats(0)}></Tab>
                            </div>
                            <div className="stats-main-section">
                                <div className="stats-main-left">
                                    {ActivityHeatmap()}
                                </div>
                                <div className="stats-half-section">
                                    <div className="stats-main-middle">
                                        <section className="stats-section">
                                            <h2 className="stats-section-title">Bästa Kategorierna</h2>
                                            <div className="stats-category-display">
                                                {categoryStats?.best.length != 0 ? categoryStats?.best.map((c)=>(
                                                    <div className="stats-category-display-cat">
                                                        <span>({c.total_sessions}) </span>
                                                        <span>{c.category_name}</span>
                                                        <div className="stats-category-bar-group">
                                                            <div className="stats-progress-bar">
                                                                <div
                                                                    className="stats-progress-fill"
                                                                    style={{ width: `${c.mastery_pct}%`, background: `${accColor(c.mastery_pct)}` }}
                                                                />
                                                            </div>
                                                            <span className="stats-mastery-pct">{Math.round(c.mastery_pct)}%</span>
                                                        </div>
                                                    </div>
                                                )) : 
                                                    <h3>Ingen Statistik</h3>
                                                }
                                            </div>
                                        </section>
                                    </div>
                                    <div className="stats-main-right">
                                        <section className="stats-section">
                                            <h2 className="stats-section-title">Sämsta Kategorierna</h2>
                                            <div className="stats-category-display">
                                                {categoryStats?.best.length != 0 ? categoryStats?.worst.map((c)=>(
                                                    <div className="stats-category-display-cat">
                                                        <span>({c.total_sessions}) </span>
                                                        <span>{c.category_name}</span>
                                                        <div className="stats-category-bar-group">
                                                            <div className="stats-progress-bar">
                                                                <div
                                                                    className="stats-progress-fill"
                                                                    style={{ width: `${c.mastery_pct}%`, background: `${accColor(c.mastery_pct)}` }}
                                                                />
                                                            </div>
                                                            <span className="stats-mastery-pct">{Math.round(c.mastery_pct)}%</span>
                                                        </div>
                                                    </div>
                                                )) :
                                                <h3>Ingen Statistik</h3>
                                                }
                                            </div>
                                        </section>
                                    </div>
                                </div>
                            </div>
                            <div className="course-grid course-grid-history" tabIndex={0} onWheel={(e) => {
                                const el = e.currentTarget;
    
                                if (el.scrollWidth <= el.clientWidth) return;
    
                                e.preventDefault();
    
                                const speed = 2; // adjust this
                                el.scrollLeft -= e.deltaY * speed;
                            }}>
                                {isLoading || stats == null || stats.mastery == null ? (
                                    <LoadingSpinner />
                                ) : (
                                    Object.entries(stats.mastery.courses).sort(([, a], [, b]) => b.session_count - a.session_count).map(([code, course]) => (
                                        <label
                                            key={course.course_code}
                                            className={`card course-card ${selectedCourse === course.course_code ? "selected" : ""} course-info-history`}
                                        >
                                            <input
                                                type="radio"
                                                name="course"
                                                value={course.course_code}
                                                checked={selectedCourse === course.course_code}
                                                onChange={() => setSelectedCourse(course.course_code)}
                                            />

                                            <div className="course-info">
                                                <span className="course-code">{course.course_code}</span>
                                                <span className="course-name">{course.course_name}</span>
                                                <div className="course-sessions">
                                                    <span className="course-qcount">
                                                        {course.session_count} Försök
                                                    </span>
                                                    <span className="course-qcount">
                                                        Träffsäkerhet: {course.mastery_pct}%
                                                    </span>
                                                </div>

                                            </div>
                                        </label>
                                    ))
                                )}
                            </div>
                            {selectedCourseData?.categories.sort((a, b) => b.session_count - a.session_count).map((category) => (
                                <div key={category.category_id} className="stats-category-row">
                                    <div className="stats-category-info">
                                        <span className="stats-category-name" title={category.category_name}>{category.category_name}</span>
                                        <span className="stats-category-name">Senast övad: {new Date(category.last_practiced).toLocaleString()}</span>
                                        <span className="stats-category-name">Försök: {category.session_count}</span>
                                    </div>
                                    <div className="stats-category-bar-group">
                                        <div className="stats-progress-bar">
                                            <div
                                                className="stats-progress-fill"
                                                style={{ width: `${category.mastery_pct}%`, background: `${accColor(category.mastery_pct)}` }}
                                            />
                                        </div>
                                        <span className="stats-mastery-pct">{Math.round(category.mastery_pct)}%</span>
                                    </div>
                                </div>
                            ))}
                            </>}
                        </div>
                    </div>
                </div>
            </main>}
        </>
    )

}

