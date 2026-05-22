import './ResultOverlay.css'
import LoadingSpinner from "../components/LoadingSpinner";
//https://www.svgrepo.com/svg/528912/close-circle
import exit from "../assets/exit.svg"
//https://www.svgrepo.com/svg/528912/close-circle -- dark color variant
import exit_dark from "../assets/exit-dark.svg"
import confetti from "canvas-confetti";
import { useNavigate, type NavigateFunction } from "react-router-dom";
import { useState, useEffect, useRef, useContext } from "react";
import { type Session } from '../pages/history'
import { DarkModeContext } from "../context/DarkModeContext";

const colours = ["#00ff44", "#00c52b", "#283145", "#e1efe2"]

interface props{
	unique_session: Session;
	onClose: () => void;
}


function increasePercentage(goal: number, setPercentage: (p: number) => void) {
    let confettiLaunched = false;
    let start: number | null = null;
    let animationFrameId: number | null = null;
    const duration = 3000;

    function easeOutQuint(t: number) {
        return 1 - Math.pow(1 - t, 5);
    }

    function animate(timestamp: number) {
        if (!start) start = timestamp;
        const progress = (timestamp - start) / duration;

        const eased = easeOutQuint(Math.min(progress, 1));
        const value = eased * goal;

        setPercentage(value);

        //console.log("Progress: " + progress + ", Eased: " + eased + ", Value: " + value);

        if (100 - value < 0.1 && !confettiLaunched) {
            confettiLaunched = true;
            confetti({
                particleCount: 75,
                angle: 60,
                spread: 55,
                origin: { x: 0, y: 1 },
                colors: colours,
                zIndex: 10000                                           
            });
            confetti({
                particleCount: 75,
                angle: 120,
                spread: 55,
                origin: { x: 1, y: 1 },
                colors: colours,
                zIndex: 10000
            })
        }

        if (progress < 1) {
            animationFrameId = requestAnimationFrame(animate);
        } else {
            setPercentage(goal);
        }
    }

    animationFrameId = requestAnimationFrame(animate);
    return () => {
        if (animationFrameId !== null) {
            cancelAnimationFrame(animationFrameId);
        }
    };
}

export default function ResultOverlay({unique_session, onClose}:props){
	const [percentage, setPercentage] = useState<number>(0);
	const [performage, setPerformage] = useState<string>("Bad");
	const cancelAnimationRef = useRef<(() => void) | null>(null);
    const ctx = useContext(DarkModeContext);

    if (!ctx) {
        return null;
    }

    const { darkMode } = ctx;


	useEffect(()=>{
        if(percentage < 30) setPerformage("Bad")
        else if(percentage < 70) setPerformage("Average")
        else if(percentage < 99) setPerformage("Amazing")
        else setPerformage("Perfect")
    },[percentage])

	useEffect(() => {
        if(!unique_session) return;

        if (!window.history.state?.viewing) {
            window.history.pushState({ viewing: true }, "");
        }

        const handlePopState = () => {
            onClose();
        };

        cancelAnimationRef.current = increasePercentage((unique_session.questions.summary.correct_count/unique_session.questions.summary.answered_count) * 100, setPercentage)

        window.addEventListener("popstate", handlePopState);

        return () => {
            window.removeEventListener("popstate", handlePopState);
            if (cancelAnimationRef.current) {
                cancelAnimationRef.current();
            }
        };

    }, [unique_session])

	function closeViewing() {
        if (cancelAnimationRef.current) {
            cancelAnimationRef.current();
        }
        confetti.reset();
        
        onClose();

        setPercentage(0);
        setPerformage("Bad");

        if (window.history.state?.viewing) {
            window.history.back();
        }
    }

	function make_questions(){
        if (!unique_session) return null;

        const questions = Object.values(unique_session.questions.questions);

        return (
            <div className="viewing-question-box">
                {questions.map((q, index) => (
                    <div key={q.id} className={`viewing-question-item ${q.is_correct ? "correct" : "wrong"}`}>
                        <div className="viewing-question-item-header">
                            <span>{index}</span>
                            <span className="viewing-result">{q.user_answer == null ? "Inget Svar" : (q.is_correct ? "Rätt" : "Fel")}</span>
                        </div>
                        <p>{q.question}</p>
                        <div className="viewing-answers">
                            <div className="viewing-answer">
                                <span>Ditt Svar</span>
                                <p className={q.is_correct ? "viewing-correct-p" : "viewing-wrong-p"}>{q.user_answer}</p>
                            </div>
                            <div className="viewing-answer">
                                <span>Rätt Svar</span>
                                <p>{q.correct_answer} {q.unit}</p>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }
	return(
        <>
            {unique_session && (
                <div className="overlay" onClick={(e) => {e.target == e.currentTarget ? closeViewing(): {}}}>
                    <div className={`viewing-popup ${performage}`}>
                        <button onClick={closeViewing} className="table-button">
                            {darkMode ? <img src={exit_dark} alt="Stäng" /> : <img src={exit} alt="Stäng" />}
                        </button>
                        <div className="viewing-heading">
                            <div className="progress-ring" style={{ "--progress": `${percentage}%` } as React.CSSProperties}>
                                <div className="inner">
                                    <h1>{Math.round(percentage)}%</h1>
                                </div>
                            </div>
                            <div className="viewing-info">
                                <div className="viewing-info-row">
                                    <div className="viewing-info-box">
                                        <span>Resultat</span>
                                        <p>{unique_session.questions.summary.correct_count}/{unique_session.questions.summary.answered_count}</p>
                                    </div>
                                    <div className="viewing-info-box">
                                        <span>Kurs</span>
                                        <p>{unique_session.course_code != null ? unique_session.course_code : unique_session.course_id}</p>
                                    </div>
                                </div>
                                <div className="viewing-info-box">
                                    <span>Datum</span>
                                    <p className="p-date">{new Date(unique_session.created_at).toLocaleString()}</p>
                                </div>
                            </div>
                        </div>
                        <div className="viewing-body">
                            {make_questions()}
                        </div>

                    </div>
                </div>
            )}
		</>
	)
}