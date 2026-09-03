import monitor_core as m

def test_miami_regression():
    c=m.KNOWN_REGRESSION
    assert m.is_relevant(c['title'],c['summary'])
    assert m.status_from_text(c['title']+' '+c['summary'])=='Seriously Injured'
    assert m.location_from_text(c['title']+' '+c['summary'])=='Florida'

def test_fatal_and_serious():
    assert m.status_from_text('cyclist killed after driver crash')=='Killed'
    assert m.status_from_text('cyclist suffered spinal cord injury and was hospitalized')=='Seriously Injured'

def test_irrelevant():
    assert not m.is_relevant('Cyclist wins race','No crash or injury reported.')

def test_duplicate_miami_reports():
    a=m.KNOWN_REGRESSION.copy(); a['url']='a'
    b={'title':'Surgeon critically hurt in bicycle crash on Rickenbacker Causeway in Key Biscayne','summary':'A South Florida surgeon was hit by a driver while riding a bicycle and rushed to Jackson Memorial Hospital.','url':'b','location':'Florida'}
    assert m.same_incident(a,b)
