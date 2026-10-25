from fastapi import FastAPI,Path,HTTPException,Query
app=FastAPI()
import json
def load_data():
    with open('a.json','r') as f:
        data=json.load(f)
    return data
@app.get("/")
def hello():
    return {'message','nice'}
@app.get('/about')
def about():
    return {'message','nihiufjdk,ce'}
@app.get('/view')
def view():
    data=load_data()
    return data
@app.get('/voter/{voter_id}')
def view_voter(voter_id:str =Path(...,description='Enter voter id',example='DUMMY-PRG-0103')):
    data=load_data()
    if voter_id in data:
        return data[voter_id]
    raise HTTPException(status_code=404,detail='Voter not found')


    
@app.get('/sort')
def sort_voters(sort_by:str=Query(...,description='sort on basis of age,distance'),order:str=Query('asc',description='sort in asc or dsc')):

    valid_fields=['age','distance']
    if sort_by not in valid_fields:
        raise HTTPException(status_code=400,detail='invalid field')
    if order not in ['asc','dsc']:
        raise HTTPException(status_code=404,detail='invalid')
    data=load_data()
    sort_order=True if order=='dsc' else False
    sorted_data=sorted(data.values(),key=lambda x:x.get(sort_by,0),reverse=sort_order)
    return sorted_data
    