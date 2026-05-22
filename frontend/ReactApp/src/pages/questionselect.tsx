import Header from "../components/Header";
import "./questionselect.css"
import Button from "../components/Button";
import { Slider } from "../components/Slider";
import Footer from "../components/footer";
import LoadingSpinner from "../components/LoadingSpinner";

//https://www.svgrepo.com/svg/529546/double-alt-arrow-down
import down from "../assets/down.svg"
//https://www.svgrepo.com/svg/529550/double-alt-arrow-up
import up from "../assets/up.svg"

import { useNavigate, type NavigateFunction } from "react-router-dom";

// from https://www.npmjs.com/package/react-multi-select-component MIT License
import { MultiSelect } from "react-multi-select-component";
import { useState } from "react";
// from https://www.svgrepo.com/svg/347916/radio-button
// and https://www.svgrepo.com/svg/327494/radio-button-on
import RadioOn from "../assets/radio-on.svg";
import RadioOff from "../assets/radio-off.svg";
import { useRef, useEffect } from "react";
import { apiFetch } from "../services/apt";


export interface courseData {
    id: number;
    name: string;
    categories: string[];
}

export interface Option {
    label: string;
    value: string;
}

export interface courses{
    courses: Record<string, courseData>
    max_questions: Record<string, Record<string, number>>
}
async function get_courses_and_categories(): Promise<courses> {
    const res = await apiFetch("/api/categories");
    const json = await res.json();
    //console.log(json)
    return json
}

function get_course_question_count(course: string, data: courses): number {
    return Object.values(data.max_questions[course]).reduce((sum, count) => sum + count, 0);
}

function distributeEvenly( total: number, categories: string[], maxMap: Record<string, number>): Record<string, number> {
    const result: Record<string, number> = {};
    categories.forEach(cat => (result[cat] = 0));
    let i = 0;
    while (total > 0) {
        const cat = categories[i % categories.length];
        if (result[cat] < maxMap[cat]) {
            result[cat]++;
            total--;
        }

        i++;

        if (categories.every(c => result[c] >= maxMap[c])) break;
    }

    return result;
}


function make_categories(course:string, data:courses, values: Record<string, number>, updateValue: (category: string, value: number) => void){
    const categories = data.courses[course].categories;

    return(
        <div className="categories-grid">{
            categories.map((category, index) => {

            const max = data.max_questions[course][category];
            //console.log(max)

            return (
                
                <div>
                <div className="stat-text">
                    <span className="stat-name">{category}</span>
                    <div className="stat-numbers">
                        <input
                            type="number"
                            name={category}
                            id={category}
                            min="0"
                            max={max}
                            onFocus={(e) => e.target.select()}
                            value={values[category] ?? 0}
                            onChange={(e) => {
                                let val = Number(e.target.value);

                                if (isNaN(val)) val = 0;
                                if (val > max) val = max;
                                if (val < 0) val = 0;

                                updateValue(category, val);
                            }}
                        />
                        <span className="stat-divider">/</span>
                        <span className="stat-max">{max}</span>
                    </div>
                </div>
                <div key={index} className="category">
                    <div className="category-input">
                        <Slider
                            min={0}
                            max={max}
                            value={values[category] ?? 0}
                            onChange={(v) => updateValue(category, v)}
                        /> 
                    </div>
                </div>
                </div>
            );
    })}</div>);
}

function simple_category(course:string, data:courses, values: Record<string, number>, setValues: (v: Record<string, number>) => void){
    const categories = data.courses[course].categories;
    const max = get_course_question_count(course,data);
    const total = Object.values(values).reduce((a, b) => a + b, 0);

    function handleChange(newTotal: number){
        const distributed = distributeEvenly(newTotal, categories, data.max_questions[course]);
        setValues(distributed);
    }

    return (
        <>
            <div className="category">
                <div className="category-input category-input-simple">
                    <Slider
                        min={0}
                        max={max}
                        value={total}
                        onChange={(v) => handleChange(v)}
                    />

                    <input
                    type="number"
                    min="0"
                    max={max}
                    value={total}
                    onFocus={(e) => e.target.select()}
                    onChange={(e) => handleChange(Number(e.target.value))}
                    />
                </div>
            </div>
            <div className="simple-data">
            {categories.map(cat => {
            const maxPerCat = data.max_questions[course][cat];
            const currentVal = values[cat] || 0;
            
            // Räkna ut procenten för progress baren (förhindra NaN om max skulle vara 0)
            const percentage = maxPerCat > 0 ? (currentVal / maxPerCat) * 100 : 0;

            return(
                <div key={cat}>
                    <div className="stat-text">
                        <span className="stat-name">{cat}</span>
                        <div className="stat-numbers">
                            <span className="stat-current">{currentVal}</span>
                            <span className="stat-divider">/</span>
                            <span className="stat-max">{maxPerCat}</span>
                        </div>
                    </div>
                    <div className="stat-progress-bg">
                        <div 
                            className="stat-progress-fill" 
                            style={{ width: `${percentage}%` }}
                        ></div>
                    </div>
                </div>
        )
    })}
</div>
        </>
  );
    
}

export default function questionselect(){
    const navigate = useNavigate();
    const [questionamount, setQuestionAmount] = useState(0);
    const [selectedCourse, setSelectedCourse] = useState<string>("");
    const [values, setValues] = useState<Record<string, number>>({});
    const [data, setData] = useState<courses | null>(null);
    const [selectedsimple, setSelectedsimple] = useState(0);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [options, setOptions] = useState<Option[]>([]);
    const [selectedCourses, setSelected] = useState<Option[]>([]);
    const [advancedQuestion, setAdvancedQuestion] = useState<boolean>(false);

    useEffect(() => {
        async function fetchData() {
            setIsLoading(true);
            const result = await get_courses_and_categories();
            setData(result);
            const courseOptions: Option[] = Object.keys(result.courses).map((courseId) => ({
                value: courseId,
                label: `${courseId} ${result.courses[courseId].name}`
            }));
            setOptions(courseOptions);
            setSelected(courseOptions);
            setIsLoading(false);
            
        }
        fetchData();
    }, []);

    useEffect(() => {
        setValues({});
        setSelectedsimple(0);
    }, [selectedCourse]);

    useEffect(() => {
        function update_question_amount(){
            const total = Object.values(values).reduce((sum, val) => sum + val, 0);
            setQuestionAmount(total);
        }
        update_question_amount();
    }, [values])

    useEffect(() => {
        if (!selectedCourse || !data || selectedsimple !== 0) return;

        const categories = data.courses[selectedCourse].categories;
        const max = get_course_question_count(selectedCourse, data);

        const clamp = (num: number, min: number, max: number) =>
            num <= min ? min : num >= max ? max : num;
        const initialTotal = max < 10 ? max : clamp(max / 2, 10, 20);

        const distributed = distributeEvenly(
            initialTotal,
            categories,
            data.max_questions[selectedCourse]
        );

        setValues(distributed);
    }, [selectedCourse, data]);

    // if (data == null || Object.keys(data.courses).length === 0) {
    //     return <h1>Loading or session expired... Please log in again.</h1>
    // }
        function handleQuickStart(percent: number) {
        if (!selectedCourse || !data) return;

        const categories = data.courses[selectedCourse].categories;
        const max = get_course_question_count(selectedCourse, data);

        const clamp = (num: number, min: number, max: number) =>
            num <= min ? min : num >= max ? max : num;

        let total = 0;

        if (percent === 1) {
            total = max;
        } else if (percent === 0.5) {
            total = clamp(Math.round(max * 0.5), 5, 20);
        } else if (percent === 0.25) {
            total = clamp(Math.round(max * 0.25), 0, 5);
        }

        const distributed = distributeEvenly(
            total,
            categories,
            data.max_questions[selectedCourse]
        );

        setValues(distributed);

        navigate("/questions", {
            state: {
                course: selectedCourse,
                values: distributed
            }
        });
    }
    function getQuickStartTotal(percent: number): number {
        if (!selectedCourse || !data) return 0;

        const max = get_course_question_count(selectedCourse, data);

        const clamp = (num: number, min: number, max: number) =>
            num <= min ? min : num >= max ? max : num;
        if (percent === 1) return max;
        if (percent === 0.5) return clamp(Math.round(max * 0.5), 1, 20);
        if (percent === 0.25) return clamp(Math.round(max * 0.25), 1, 5);

        return 0;
    }

    function updateValue(category: string, value: number) {
        setValues(prev => ({
            ...prev,
            [category]: value
        }));
    }
    function go_to_questions(navigate : NavigateFunction){
        navigate("/questions", {
            state:{
                course: selectedCourse,
                values: values
            }
        })
    }

    
    return(
        <>
            <div className="maindiv-qs">
                <div className="form">
                    <div className="course-selection">
                        <div className="course-selection-header">
                            <h1>Välj kurs och antal frågor</h1>
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
                        </div>
                        <div className="course-grid" tabIndex={0} onWheel={(e) => {
                            const el = e.currentTarget;

                            if (el.scrollWidth <= el.clientWidth) return;

                            e.preventDefault();

                            const speed = 2; // adjust this
                            el.scrollLeft -= e.deltaY * speed;
                        }}>
                            {isLoading || data == null ? (
                                <LoadingSpinner />
                            ) : (
                                Object.keys(data.courses)
                                    .filter((c) => selectedCourses.some((selected: Option) => selected.value === c))
                                    .map((c) => (
                                    <label
                                        key={c}
                                        className={`card course-card ${selectedCourse === c ? "selected" : ""}`}
                                    >
                                        <input
                                        type="radio"
                                        name="course"
                                        value={c}
                                        checked={selectedCourse === c}
                                        onChange={() => setSelectedCourse(c)}
                                        />
                                        <div className="course-info">
                                            <span className="course-code">{c}</span>
                                            <span className="course-name">{data.courses[c].name}</span>
                                            <span className="course-qcount">{get_course_question_count(c, data)} frågor</span>
                                        </div>
                                    </label>
                                    ))
                            )}
                        </div>
                    </div>
                        {
                        selectedCourse && data != null &&(
                            <div className="category-select">
                                <h3>Snabb Start</h3>
                                <div className="fast-start-buttons">
                                    <div className="practicebutton">
                                        <Button text={`${getQuickStartTotal(0.25)} Frågor`} onClick={() => handleQuickStart(0.25)}></Button>
                                    </div>
                                    <div className="practicebutton">
                                        <Button text={`${getQuickStartTotal(0.5)} Frågor`} onClick={() => handleQuickStart(0.5)}></Button>
                                    </div>
                                    <div className="practicebutton">
                                        <Button text={`${getQuickStartTotal(1)} Frågor`} onClick={() => handleQuickStart(1)}></Button>
                                    </div>
                                </div>
                                <div className="practicebutton">
                                    <Button text="Avancerade Val" onClick={() => setAdvancedQuestion(!advancedQuestion)} color="var(--secondary-button)" hover="var(--secondary-button-hover)" img={advancedQuestion ? [up, "Göm Avanserade val"] : [down, "Visa Avanserade val"]}></Button>
                                </div>
                                {advancedQuestion &&
                                <div className="category-select" style={{background: "#a37de527"}}>
                                    <div className="radios-qs">
                                        <div>
                                            <label>
                                                <input type="radio" name="simple" value={0} checked={selectedsimple == 0} onChange={() => setSelectedsimple(0)}/>
                                                <span><img src={selectedsimple == 0 ? RadioOn: RadioOff} alt={selectedsimple == 0 ? "Alternativet Alla Vald": "Alternativet Alla ej vald"}/> Alla</span>
                                            </label>
                                        </div>
                                        <div>
                                            <label>
                                                <input type="radio" name="simple" value={1} checked={selectedsimple == 1} onChange={() => setSelectedsimple(1)}/>
                                                <span><img src={selectedsimple == 1 ? RadioOn: RadioOff} alt={selectedsimple == 0 ? "Alternativet specifiera Vald": "Alternativet specifiera ej vald"}/> Specifiera</span>
                                            </label>
                                        </div>
                                    </div>
                                    <span>Mängd Frågor:</span>
                                    {selectedsimple == 0 ? simple_category(selectedCourse, data, values, setValues) : make_categories(selectedCourse, data, values, updateValue)}
                                    <div className="practicebuttonhousing">
                                        <div className="practicebutton">
                                            <Button text="Öva" onClick={() => {go_to_questions(navigate)}} disabled={questionamount == 0}></Button>
                                        </div>
                                    </div>
                                </div>}
                            </div>
                            ) 
                        }
                        <Footer></Footer>
                </div>
                
            </div>
            
        </>
    )


}

