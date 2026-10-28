"""How much more does a team lose to injuries than moving the absent players' minutes to weaker teammates predicts?

Season level, 2016-17..2025-26 (300 team-seasons, season fixed effects): team margin per game on the rotation's full-strength
rating (prior-season player ratings) and on the rating change that teams._roster_with_injuries gives for the games each
player missed (availability = games played / team games). The ratio of the two coefficients is predict.INJURY_AMP.
Caveat: games played also reflects mid-season trades, so some roster churn is counted as absence.

Run: .venv/bin/python scripts/backtest_injury_amp.py
"""

import numpy as np, pandas as pd, psycopg
from ballstats import config, teams
with psycopg.connect(config.DSN) as c:
    st=pd.DataFrame(c.execute("select season,player_id,team,gp,minutes from feat.player_stats where season<>'career'").fetchall(),columns=["season","pid","team","gp","min"]).astype({"min":float})
    rt=pd.DataFrame(c.execute("select season,player_id,ovr from feat.player_rating").fetchall(),columns=["season","pid","ovr"]).astype({"ovr":float})
    g=pd.DataFrame(c.execute("select season,team,count(*),avg(team_score-opp_score) from live.game where season_type=2 and completed group by 1,2").fetchall(),columns=["season","team","n","m"]).astype({"m":float})
def ss(y): return f"{y}-{str(y+1)[2:]}"
rows=[]
for y in range(2016,2026):
    s,p=ss(y),ss(y-1)
    prior=rt[rt.season==p].set_index("pid").ovr; repl=prior.quantile(.25)
    for _,t in g[g.season==s].iterrows():
        x=st[(st.season==s)&(st.team==t.team)].copy()
        x["ovr"]=x.pid.map(prior).fillna(repl)
        x["mpg"]=x["min"]/x.gp.clip(lower=1)
        x=x.sort_values("mpg",ascending=False).head(9)       # rotation by minutes per game played
        w=x.mpg/x.mpg.sum()
        miss=(1-(x.gp/t.n)).clip(0,1)
        R=float((w*x.ovr).sum())
        lost=float((w*miss*(x.ovr-repl).clip(lower=0)).sum())     # mechanical: rating lost, vs a replacement-level player
        star=x.assign(w=w,miss=miss).sort_values("ovr",ascending=False).head(3)
        lost_star=float((star.w*star.miss*(star.ovr-repl).clip(lower=0)).sum())
        # production mechanism: lost minutes go to weaker teammates (teams._roster_with_injuries), availability = share of games played
        ev=st[(st.season==s)&(st.team==t.team)].copy(); ev["ovr"]=ev.pid.map(prior).fillna(repl); ev["off"]=ev.ovr; ev["def"]=ev.ovr
        ev["min"]=ev["min"]/ev.gp.clip(lower=1)   # minutes per game played = full-strength minutes
        top=ev.sort_values("min",ascending=False).head(9)
        av=(top.set_index("pid").gp/t.n).clip(0,1).to_dict()
        hurt={k:v for k,v in av.items() if v<1}
        radj=teams._roster_with_injuries(top,ev,hurt,pd.Series({"ovr":repl,"off":repl,"def":repl}))["ovr"]
        full=float(np.average(top.ovr,weights=top["min"]))
        starset=set(top.sort_values("ovr",ascending=False).head(3).pid)
        hs={k:v for k,v in hurt.items() if k in starset}; ho={k:v for k,v in hurt.items() if k not in starset}
        r_s=teams._roster_with_injuries(top,ev,hs,pd.Series({"ovr":repl,"off":repl,"def":repl}))["ovr"]-full
        r_o=teams._roster_with_injuries(top,ev,ho,pd.Series({"ovr":repl,"off":repl,"def":repl}))["ovr"]-full
        rows.append({"mech":radj-full,"mech_star":r_s,"mech_other":r_o,"Rfull":full,"season":y,"team":t.team,"m":t.m,"R":R,"lost":lost,"lost_star":lost_star,"lost_other":lost-lost_star})
d=pd.DataFrame(rows)
# season fixed effects: demean within season
for c_ in ["m","R","lost","lost_star","lost_other","mech","mech_star","mech_other","Rfull"]: d[c_]=d[c_]-d.groupby("season")[c_].transform("mean")
def fit(cols):
    X=d[cols].to_numpy(); b=np.linalg.lstsq(X,d.m,rcond=None)[0]; e=d.m-X@b; se=np.sqrt(np.diag(np.linalg.inv(X.T@X))*e.var()); return dict(zip(cols,zip(b.round(3),(b/se).round(1)))), round(float(e.std()),2)
print(len(d),"team-seasons"); print(d[["R","lost","lost_star"]].describe().round(2).loc[["mean","std"]])
print(fit(["Rfull","mech"])); print(fit(["Rfull","mech_star","mech_other"]))
