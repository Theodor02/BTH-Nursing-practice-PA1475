import Header from "../components/Header";
import Button from "../components/Button";
import LoadingSpinner from "../components/LoadingSpinner";
import Calculator from "../components/Calculator"
import ResultOverlay from "../components/ResultOverlay";
import "./questions.css"
import { use, useState, useContext, useRef} from "react";
import { useNavigate, useLocation, type NavigateFunction } from "react-router-dom";
import { useEffect } from "react";
import { type Session } from "./history"
import { DarkModeContext } from "../context/DarkModeContext";
import { useLeaveGuard } from "../context/leaveGuardContext";
import { apiFetch } from "../services/apt";

//https://www.svgrepo.com/svg/529546/double-alt-arrow-down
import down from "../assets/down.svg"
//https://www.svgrepo.com/svg/529550/double-alt-arrow-up
import up from "../assets/up.svg"

//https://www.svgrepo.com/svg/529421/calculator-minimalistic
import calc from "../assets/calculator.svg"
//https://www.svgrepo.com/svg/529739/notebook-bookmark
import help from "../assets/help.svg"
//https://www.svgrepo.com/svg/529183/ruler
import units_img from "../assets/units.svg"

//https://www.svgrepo.com/svg/529799/refresh
import refresh from "../assets/refresh.svg"
//https://www.svgrepo.com/svg/529940/star-circle
import q_results from "../assets/results.svg"
//https://www.svgrepo.com/svg/529821/round-arrow-right
import right from "../assets/question-right.svg"
//https://www.svgrepo.com/svg/529818/round-arrow-left
import left from "../assets/question-left.svg"
//https://www.svgrepo.com/svg/528887/check-circle
import checking from "../assets/question-checking.svg"
//https://www.svgrepo.com/svg/529849/sad-circle
import wrong from "../assets/wrong.svg"
//https://www.svgrepo.com/svg/530040/verified-check
import correct from "../assets/correct.svg"

//https://www.svgrepo.com/svg/529799/refresh -- dark mode variant
import refresh_dark from "../assets/refresh-dark.svg"
//https://www.svgrepo.com/svg/529940/star-circle -- dark mode variant
import q_results_dark from "../assets/results-dark.svg"
//https://www.svgrepo.com/svg/529821/round-arrow-right -- dark mode variant
import right_dark from "../assets/question-right-dark.svg"
//https://www.svgrepo.com/svg/529818/round-arrow-left -- dark mode variant
import left_dark from "../assets/question-left-dark.svg"
//https://www.svgrepo.com/svg/528887/check-circle -- dark mode variant
import checking_dark from "../assets/question-checking-dark.svg"
//https://www.svgrepo.com/svg/529849/sad-circle -- dark mode variant
import wrong_dark from "../assets/wrong-dark.svg"
//https://www.svgrepo.com/svg/530040/verified-check -- dark mode variant
import correct_dark from "../assets/correct-dark.svg"

type Question = {
    id: string;
    template_id: string;
    question: string;
    unit: string;
    hints: string[];
    link: string;
    answer_type?: string;
};

type Result = {
    correct: boolean;
    correctValue: boolean;
    userAnswer: UserAnswer;
    correctAnswer: string | number;
    hasUnit: boolean;
    correctUnit: boolean;
};

interface Unit {
    name: string;
    aliases: string[];
}

type UserAnswer = string;


export default function Questions(){
    
    const location = useLocation();
    const navigate = useNavigate();

    const state = location.state || {};
    
    const course = state.course;
    const values = state.values;

    useEffect(() => {
        if (!course || !values) {
            navigate("/index", { replace: true });
        }
    }, [course, navigate]);


    const [index, setIndex] = useState(0)
    
    const [questions, setQuestions] = useState<Question[]>([]);
    const [attemptId, setAttemptId] = useState<string | null>(null);

    const [selectedHelp, setSelectedHelp] = useState(0);

    const [trueAnswers, setTrueAnswers] = useState<string[]>([]);

    const [currentAnswers, setCurrentAnswers] = useState<string[]>([]);

    const [trueResults, setTrueResults] = useState<(Result | null)[]>([]);

    const [results, setResults] = useState<(Result | null)[]>([]);

    const [isOpen, setOpen] = useState(false)

    const [tipsArray, setTipsArray] = useState<number[][]>([]);

    const [ session, setSession ] = useState<Session | null>(null); 

    const [courseCode, setCourseCode] = useState<string>("");

    const [units, setUnits] = useState<Unit[]>([]);

    const [visibleUnits, setVisibleUnits] = useState<Boolean[]>([])

    const ctx = useContext(DarkModeContext);

    if (!ctx) {
        return null;
    }

    const { darkMode } = ctx;


    if (!course || !values) {
        return null;
    }

    const { setShouldBlock, setOnLeave } = useLeaveGuard();

    useEffect(() => {
        const hasUnsaved = currentAnswers.some(a => a !== "") && !session;

        setShouldBlock(hasUnsaved);

        setOnLeave(() => {
            return () => {
                if (!attemptId) return;

                const formattedAnswers: Record<string, string> = {};
                questions.forEach((q, i) => {
                    if (trueAnswers[i] !== "") {
                        formattedAnswers[q.id] = trueAnswers[i];
                    }
                    else if (currentAnswers[i] !== "") {
                        formattedAnswers[q.id] = currentAnswers[i];
                    }
                });

                navigator.sendBeacon(
                    "/api/attempts/submit",
                    new Blob([JSON.stringify({
                        attempt_id: attemptId,
                        answers: formattedAnswers
                    })], { type: "application/json" })
                );
            };
        });

        return () => {
            setShouldBlock(false);
            setOnLeave(undefined);
        };
    }, [currentAnswers, session, attemptId, questions]);

    useEffect(() => {
        const controller = new AbortController();
        let active = true;

        async function fetchQuestions() {
            try {
                const res = await apiFetch("/api/questions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    signal: controller.signal,
                    body: JSON.stringify({
                        questions_request: {
                            course: {
                                [course]: values
                            }
                        },
                        session_meta: {
                            persist: true
                        }
                    })
                });

                const data = await res.json();

                if (!active) return;

                if (!res.ok || data.error) {
                    console.error("Error fetching questions:", data.error || res.statusText);
                    return;
                }

                setAttemptId(data.attempt_id);

                const flatQuestion: Question[] = [];

                for (const courseKey in data.questions) {
                    for (const categoryKey in data.questions[courseKey]) {
                        flatQuestion.push(...data.questions[courseKey][categoryKey]);
                    }
                }
                //console.log(data)

                setCourseCode(Object.keys(data.questions)[0])

                setQuestions(flatQuestion);

                const tipsInit = flatQuestion.map(q =>
                    Array(q.hints.length).fill(0)   
                );

                setTipsArray(tipsInit);

                const resunits = await apiFetch("/api/units", {
                    method: "GET",
                    headers: { "Content-Type": "application/json" },
                    signal: controller.signal
                });

                const dataunits = await resunits.json();

                console.log(dataunits)

                if (!active) return;

                if (!resunits.ok || dataunits.error) {
                    console.error("Error fetching questions:", dataunits.error || resunits.statusText);
                    return;
                }

                setVisibleUnits(Array(dataunits.length).fill(false))

                setUnits(dataunits);

            } catch (err) {
                if (err instanceof Error && err.name === 'AbortError') return;
                console.error("Network error while fetching questions:", err);
            }
        }
        fetchQuestions();

        return () => {
            active = false;
            controller.abort();
        };
    }, [course, values]);
    

    useEffect(() => {
        if (questions.length > 0) {
            setCurrentAnswers(Array(questions.length).fill(""));
            setTrueAnswers(Array(questions.length).fill(""));
            setResults(Array(questions.length).fill(null));
            setTrueResults(Array(questions.length).fill(null));
        }
    }, [questions]);

    useEffect(() => {
        if (trueResults[index] === null) {
            setTrueResults(prev => {
                const updated = [...prev];
                updated[index] = results[index];
                return updated;
            });
        }
    }, [results]);
    

    if (questions.length === 0) {
        return (
            <>
                <div className="maindiv">
                    <div className="questionbox">
                        <LoadingSpinner />
                    </div>
                    <div className="help-wrapper">
                        <div className="help-options">
                            <LoadingSpinner />
                        </div>  
                    </div>
                </div>
            </>
        );
    }
    

    function handleAnswerChange(value: string) {
        const newAnswers = [...currentAnswers];
        newAnswers[index] = value;
        setCurrentAnswers(newAnswers);
    }

    

    async function handleSubmitCurrent(currentIndex:number) {
        //console.log("Testing handleSubmitCurrent, svarade:", answers[index]);
        const q = questions[currentIndex];
        const userAnswer = currentAnswers[currentIndex];

        try {
            const res = await apiFetch("/api/questions/grade", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    attempt_id: attemptId,
                    question_id: q.id,
                    user_answer: userAnswer
                })
            });
            
             if (!res.ok) {
                console.error("Error grading question:", res.statusText);
                return;
            }

             const data = await res.json();

            const result: Result = {
                correct: data.correct,
                correctValue: data.correctValue,
                userAnswer: userAnswer,
                correctAnswer: data.correctAnswer,
                hasUnit: data.hasUnit,
                correctUnit: data.correctUnit
            };
            //console.log(result)
            const newResults = [...results];
            newResults[currentIndex] = result;
            setResults(newResults);

            if (trueAnswers[currentIndex] === "") {
                setTrueAnswers(prev => {
                    const updated = [...prev];
                    updated[currentIndex] = userAnswer;
                    return updated;
                });
            }

        } catch (err) {
            console.error("Network error while grading question:", err);
        }
    }
    async function handleSubmitAll() {
        const formattedAnswers: Record<string, string> = {};

        questions.forEach((q, i) => {
            const value = trueAnswers[i];
            console.log(value)
            if (value !== "") {
                formattedAnswers[q.id] = value;
            }
        });

        const res = await apiFetch("/api/attempts/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                attempt_id: attemptId,
                answers: formattedAnswers
            })
        });

        const data = await res.json();

        if (!res.ok) {
            console.error("Error submitting all answers:", data.error || res.statusText);
            return;
        }

        const session = make_session(data);
        setSession(session);
        setOpen(true);

        //console.log("Submission successful:", data);
    }

    function handleRevealHint(qIndex: number, hintIndex: number) {
        setTipsArray(prev => {
            const newArr = [...prev];
            const inner = [...newArr[qIndex]];
            inner[hintIndex] = 1;
            newArr[qIndex] = inner;
            return newArr;
        });
    }

    function tips(){
        const currentQuestion = questions[index];
        return(
            <>
                <h2 style={{marginBottom: "20px", marginTop: "10px"}}>Klicka på en ledtråd!</h2>
                {currentQuestion.hints.map((hint, i) => (
                    <div className="hints">
                        <span>{i + 1}.</span>
                        <p key={i} className={`hint-text ${tipsArray[index]?.[i] ? "revealed" : ""}`} onClick={() => {handleRevealHint(index, i)}}>{hint}</p>
                    </div>
                ))}
            </>
        )
    }

    function units_panel(){
        return(
            <>
                <h2 style={{marginBottom: "20px", marginTop: "10px"}}>Se alla enheter!</h2>
                {units.map((u, index) => (
                    <div className="the-units">
                        <span onClick={() => setVisibleUnits(prev => prev.map((value, i) => i === index ? !value : value))}>
                            <img src={visibleUnits[index] ? up : down} alt="Ner pil" /> {u.name}
                        </span>
                        {visibleUnits[index] ? u.aliases.map((alias)=>(
                            <p>{alias}</p>
                        )): <></>}
                    </div>
                ))}
            </>
        )
    }

    const noncorrectedCount = results.filter(a => a === null).length; // amount of unanswered questions

    function make_session(data: any): Session {
        const questionsRecord: Record<string, any> = {};
        questions.forEach((q, i) => {
            questionsRecord[q.id] = {
                id: q.id,
                template_id: q.template_id,
                question: q.question,
                correct_answer: trueResults[i]?.correctAnswer ?? 0,
                user_answer: trueResults[i]?.userAnswer ?? "",
                unit: q.unit,
                tolerance: 0,
                is_correct: trueResults[i]?.correct ?? false,
                is_scored: true,
                variables: {}
            };
        });

        return {
            id: data.session_id ?? 0,
            user_id: data.user_id ?? 0,
            course_id: data.course_id ?? 0,
            course_code: courseCode,
            category_name: "",
            category_names: [],
            category_id: data.category_id ?? 0,
            created_at: new Date().toISOString(),
            score: data.score ?? "",
            questions: {
                attempt_id: attemptId ?? "",
                questions: questionsRecord,
                summary: {
                    answered_count: data.answered_count ?? 0,
                    correct_count: data.correct_count ?? 0,
                    scored_count: data.scored_count ?? 0,
                    score: data.score ?? 0,
                }
            }
        };
    }

    return(
        <>
            {isOpen && session && <ResultOverlay unique_session={session} onClose={() => navigate("/home")} />}
            <main>
            <div className="maindiv">
                <div className={`questionbox ${results[index]?.correct === true ? "correct-glow" : results[index]?.correct === false ? "wrong-glow" : ""}`}
                    style={
                        results[index] ? (
                            results[index]?.correct == true ? {border: "2px solid var(--glow-correct)"} : {border: "2px solid var(--glow-wrong)"}
                            ): ({})}>
                    <div className="topline">
                        <span className={`${results[index]?.correct === true ? "correct-span" : results[index]?.correct === false ? "wrong-span" : ""}`} style={{fontSize: "1rem"}}>{
                                results[index] == null ? "" :
                                (results[index]?.correct === true && questions[index]?.answer_type === "time_of_day")
                                ? (darkMode
                                    ? <img src={correct_dark} alt="Korrekt" className="correcting-icon"/>
                                    : <img src={correct} alt="Korrekt" className="correcting-icon"/>
                                    )

                                : (!results[index].correctValue
                                    ? (darkMode
                                        ? <img src={wrong_dark} alt="Fel" className="correcting-icon"/>
                                        : <img src={wrong} alt="Fel" className="correcting-icon"/>
                                        )
                                    : !results[index].hasUnit
                                        ? (darkMode
                                            ? <img src={correct_dark} alt="Korrekt" className="correcting-icon"/>
                                            : <img src={correct} alt="Korrekt" className="correcting-icon"/>
                                            )
                                        : results[index].correctUnit
                                            ? (darkMode
                                                ? <img src={correct_dark} alt="Korrekt" className="correcting-icon"/>
                                                : <img src={correct} alt="Korrekt" className="correcting-icon"/>
                                                )
                                            : /[a-zA-Z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF]/.test(results[index].userAnswer)
                                                ? (darkMode
                                                    ? <>
                                                        <img src={wrong_dark} alt="Fel" className="correcting-icon"/> Rätt Svar med Fel Enhet!
                                                        </>
                                                    : <>
                                                        <img src={wrong} alt="Fel" className="correcting-icon"/> Rätt Svar med Fel Enhet!
                                                        </>
                                                    )
                                                : (darkMode
                                                    ? <>
                                                        <img src={wrong_dark} alt="Fel" className="correcting-icon"/> Du Har Inte Skrivit Någon Enhet!
                                                        </>
                                                    : <>
                                                        <img src={wrong} alt="Fel" className="correcting-icon"/> Du Har Inte Skrivit Någon Enhet!
                                                        </>
                                                    )
                                    )
                            }
                            </span>
                        <h1>Fråga {index+1}/{questions.length}</h1>
                        <div className="redo-btn">
                            {(results[index] != null && !results[index].correct) && (
                                <button className="table-button" onClick={()=>{
                                    setResults(prev => {
                                        const updated = [...prev];
                                        updated[index] = null;
                                        return updated;
                                    });
                                }} style={{ '--btn-bg': 'blue' } as React.CSSProperties} >
                                    {darkMode ? <img src={refresh_dark} alt="Försök igen" /> : <img src={refresh} alt="Försök igen" />}
                                </button>
                            )}
                        </div>
                    </div>
                    
                    {/* <hr style={{ height: 2, backgroundColor: "gray", border: "none", width: "95%", flexShrink: 0 }} /> */}

                    <div className="question-text">
                        <p>{questions[index].question}</p>
                    </div>
                    <div className="input-container">
                        <input type="text" value={currentAnswers[index]} onChange={(e) => handleAnswerChange(e.target.value)} placeholder={
                                questions[index].answer_type === "duration" ? "t.ex. 1h 20min, 90min, 2 timmar" :
                                questions[index].answer_type === "time_of_day" ? "t.ex. 17:30" :
                                ""
                            } disabled={results[index] != null} onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) =>{
                                if(e.key === "Enter"){
                                    e.preventDefault();
                                    handleSubmitCurrent(index);
                                }

                            }}/>
                        <div className="next">
                            <button className="table-button nav-button" onClick={() => setIndex(index - 1)} disabled={index === 0}>
                                {darkMode ? <img src={left_dark} alt="Föregående " /> : <img src={left} alt="Föregående " />}
                            </button>
                            {noncorrectedCount !== 0 ? (
                                    results[index] == null && (
                                    <button className="table-button" onClick={()=>handleSubmitCurrent(index)} disabled={currentAnswers[index] === ""}>
                                        {darkMode ? <img src={checking_dark} alt="Rätta fråga" /> : <img src={checking} alt="Rätta fråga" />}
                                    </button>
                                    )
                                ) : (
                                    (
                                    <button className="table-button" onClick={handleSubmitAll} style={{ '--btn-bg': 'lightgreen' } as React.CSSProperties} >
                                        {darkMode ? <img src={q_results_dark} alt="Klar" /> : <img src={q_results} alt="Klar" />}
                                    </button>
                                    )
                            )}
                            <button
                                className="table-button nav-button"
                                onClick={() => {
                                if (questions.length - 1 !== index) {
                                    setIndex(index + 1);
                                }
                                }}
                                disabled={
                                    questions.length - 1 === index
                                }>
                                {darkMode ? <img src={right_dark} alt="Nästa" /> : <img src={right} alt="Nästa" />}
                            </button>
                        </div>
                    </div>
                    
                </div>
                <div className="help-wrapper">
                    <div className="help">
                        <div className="radios">
                            <label>
                                <input type="radio" name="help" value={0} checked={selectedHelp == 0} onChange={() => setSelectedHelp(0)}/>
                                <span  style={{background: 'linear-gradient(90deg, crimson, #940000)'}}><img src={calc} alt="Miniräknare" /></span>
                            </label>
                        </div>
                        <div className="radios">
                            <label>
                                <input type="radio" name="help" value={0} checked={selectedHelp == 1} onChange={() => setSelectedHelp(1)}/>
                                <span  style={{background: 'linear-gradient(90deg, #a2dda2, #84cef3)'}}><img src={help} alt="Tips" /></span>
                            </label>
                        </div>
                        <div className="radios">
                            <label>
                                <input type="radio" name="help" value={0} checked={selectedHelp == 2} onChange={() => setSelectedHelp(2)}/>
                                <span  style={{background: 'linear-gradient(90deg, orange, #ca7300)'}}><img src={units_img} alt="Enheter" /></span>
                            </label>
                        </div>
                    </div>
                    <div className="help-options">
                        {selectedHelp == 0 && <Calculator/>}
                        {selectedHelp == 1 && <div key={index} className="hints-wrap">
                            <div className="the-hints">{tips()}</div>
                                {questions[index].link && 
                                    <div style={{height: "10%", width: "90%", minHeight: "40px"}}>
                                        <Button text={questions[index].link.startsWith("https://www.fass.se") ? "FASS" : "Mer Hjälp"} onClick={() => window.open(questions[index].link, "_blank")} />
                                    </div>}
                            </div>
                        }
                        {selectedHelp == 2 && <div className="units-wrap">
                            {units_panel()}
                        </div>}
                    </div>  
                </div>
            </div>
            </main>
            
        </>
    )
}